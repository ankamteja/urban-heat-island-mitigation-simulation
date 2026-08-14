"""
Step 2 - Regression model.

Target: LST (Land Surface Temperature, degrees C).

Why LST and not Heat_Risk: preprocess.py verifies that
    Heat_Risk == unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)
holds to ~1e-15. Heat_Risk is therefore a closed-form function of LST and
NDVI, and NDVI is one of our features - so "predicting" Heat_Risk from NDVI
plus location would be algebraic identity recovery, not learning. LST is the
physically measured quantity, it is what the dashboard renders as
`temperature`, and it is measured independently of NDVI.

Two feature sets are evaluated, and two split strategies, because they answer
different questions and only one of each is honest for a given use case.
See README section 3.

Input : Results/preprocessed.csv
Output: Models/heat_risk_model.pkl
        Results/metrics.md, Results/metrics.json
        Results/pred_vs_actual.png, Results/feature_importances.png

Run:  python scripts/train_regression.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # headless: write files, never open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neighbors import NearestNeighbors

# ---------------------------------------------------------------------------
# Configuration - all seeds fixed for reproducibility
# ---------------------------------------------------------------------------
RANDOM_STATE = 42
TEST_FRACTION = 0.20
N_SPATIAL_NEIGHBOURS = 8  # k for the spatial-lag feature
SPATIAL_BLOCK_GRID = 6  # 6x6 = 36 contiguous blocks for the blocked split
RF_N_ESTIMATORS = 300

TARGET = "LST"
# NDBI and Vegetation come from the corrected Earth Engine export and were
# previously discarded by preprocess.py, so the model never saw them. Measured
# on the current dataset, NDBI is the single strongest linear predictor of
# surface temperature available:
#
#     NDBI        vs LST   +0.609
#     Vegetation  vs LST   -0.455
#     NDVI        vs LST   -0.398
#
# The module README used to explain the weak NDVI signal as an artifact of the
# uncorrected export. That explanation expired when the corrected data landed;
# the real gap was a missing feature.
BASE_FEATURES = ["NDVI", "NDBI", "Vegetation", "Latitude", "Longitude"]
LAG_FEATURE = "LST_lag_k8"

# Degrees -> metres, for turning lon/lat into an approximately isotropic space
# so that k-nearest-neighbour distances are meaningful.
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON_EQUATOR = 111_320.0

MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent

sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402  (path must be set before import)

RESULTS_DIR = MODULE_DIR / "Results"
MODELS_DIR = MODULE_DIR / "Models"
INPUT_CSV = RESULTS_DIR / "preprocessed.csv"
MODEL_PATH = MODELS_DIR / "heat_risk_model.pkl"


def to_metric_coords(df: pd.DataFrame) -> np.ndarray:
    """Project lon/lat to a local metric plane (equirectangular about the mean lat)."""
    mean_lat_rad = np.radians(df["Latitude"].mean())
    x = df["Longitude"].to_numpy() * M_PER_DEG_LON_EQUATOR * np.cos(mean_lat_rad)
    y = df["Latitude"].to_numpy() * M_PER_DEG_LAT
    return np.column_stack([x, y])


def random_split(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Plain random 80/20 split."""
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.permutation(n)
    n_test = int(round(n * TEST_FRACTION))
    return idx[n_test:], idx[:n_test]


def spatial_block_split(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Hold out whole contiguous spatial blocks instead of scattered cells.

    A random split on a 100 m grid is optimistic: adjacent cells are nearly
    duplicates, so almost every test cell has a near-twin in training. Blocking
    breaks that and gives an honest "new neighbourhood" generalisation estimate.
    """
    lon_bin = pd.qcut(df["Longitude"], SPATIAL_BLOCK_GRID, labels=False)
    lat_bin = pd.qcut(df["Latitude"], SPATIAL_BLOCK_GRID, labels=False)
    block = (lon_bin * SPATIAL_BLOCK_GRID + lat_bin).to_numpy()

    blocks = np.unique(block)
    rng = np.random.default_rng(RANDOM_STATE)
    rng.shuffle(blocks)

    target_test = int(round(len(df) * TEST_FRACTION))
    test_mask = np.zeros(len(df), dtype=bool)
    for b in blocks:
        if test_mask.sum() >= target_test:
            break
        test_mask |= block == b

    return np.flatnonzero(~test_mask), np.flatnonzero(test_mask)


def spatial_lag(
    coords: np.ndarray,
    values: np.ndarray,
    train_idx: np.ndarray,
    query_idx: np.ndarray,
    is_train_query: bool,
) -> np.ndarray:
    """
    Mean target value of the k nearest *training* cells.

    Neighbours are drawn only from the training set - including test cells here
    would leak the test target into its own feature. When querying training
    rows we request k+1 and drop the self-match.
    """
    nn = NearestNeighbors(n_neighbors=N_SPATIAL_NEIGHBOURS + (1 if is_train_query else 0))
    nn.fit(coords[train_idx])
    _, nbr = nn.kneighbors(coords[query_idx])
    if is_train_query:
        nbr = nbr[:, 1:]  # drop self
    return values[train_idx][nbr].mean(axis=1)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def build_models() -> dict[str, object]:
    return {
        "LinearRegression": LinearRegression(),
        "RandomForest": RandomForestRegressor(
            n_estimators=RF_N_ESTIMATORS,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found - run scripts/preprocess.py first."
        )
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df):,} preprocessed rows")

    missing = set(BASE_FEATURES) - set(df.columns)
    if missing:
        raise ValueError(
            f"preprocessed.csv is missing feature columns {sorted(missing)} - "
            "it was produced by an older preprocess.py. Re-run it."
        )

    ndvi_corrected = shared.ndvi_looks_corrected(float(df["NDVI"].max()))
    if not ndvi_corrected:
        print(
            "WARNING: NDVI looks uncorrected (max "
            f"{df['NDVI'].max():.3f}). Coefficients and importances on NDVI are "
            "attenuated accordingly."
        )

    coords = to_metric_coords(df)
    y = df[TARGET].to_numpy()

    splits = {
        "random_80_20": random_split(len(df)),
        "spatial_block": spatial_block_split(df),
    }

    rows: list[dict] = []
    artefacts: dict[str, object] = {}

    for split_name, (train_idx, test_idx) in splits.items():
        print(
            f"\nSplit '{split_name}': {len(train_idx):,} train / {len(test_idx):,} test"
        )

        lag_train = spatial_lag(coords, y, train_idx, train_idx, is_train_query=True)
        lag_test = spatial_lag(coords, y, train_idx, test_idx, is_train_query=False)

        feature_sets = {
            "base": (
                df.loc[train_idx, BASE_FEATURES].to_numpy(),
                df.loc[test_idx, BASE_FEATURES].to_numpy(),
                BASE_FEATURES,
            ),
            "base+spatial_lag": (
                np.column_stack([df.loc[train_idx, BASE_FEATURES].to_numpy(), lag_train]),
                np.column_stack([df.loc[test_idx, BASE_FEATURES].to_numpy(), lag_test]),
                BASE_FEATURES + [LAG_FEATURE],
            ),
        }

        for fs_name, (x_train, x_test, names) in feature_sets.items():
            for model_name, model in build_models().items():
                model.fit(x_train, y[train_idx])
                metrics = evaluate(y[test_idx], model.predict(x_test))
                rows.append(
                    {
                        "split": split_name,
                        "features": fs_name,
                        "model": model_name,
                        **metrics,
                    }
                )
                print(
                    f"  {model_name:<17} {fs_name:<16} "
                    f"RMSE {metrics['rmse']:.4f}  MAE {metrics['mae']:.4f}  "
                    f"R2 {metrics['r2']:.4f}"
                )
                artefacts[f"{split_name}|{fs_name}|{model_name}"] = (
                    model,
                    names,
                    test_idx,
                )

    results = pd.DataFrame(rows)

    # -----------------------------------------------------------------------
    # Canonical saved model.
    #
    # Deliberately the BASE feature set (no spatial lag) on the random split:
    # base is the only configuration valid for the actual use case - estimating
    # temperature for a cell from its vegetation and location. The spatial-lag
    # variant needs neighbouring cells' measured LST, so it can only gap-fill
    # inside an area already surveyed, not predict anywhere new.
    #
    # Filename kept as heat_risk_model.pkl for continuity with the module spec;
    # the target is LST. Heat_Risk is recoverable exactly from LST + NDVI via
    # the identity in preprocess.py.
    # -----------------------------------------------------------------------
    canonical_key = "random_80_20|base|RandomForest"
    canonical_model, canonical_names, canonical_test_idx = artefacts[canonical_key]
    joblib.dump(
        {
            "model": canonical_model,
            "target": TARGET,
            "features": canonical_names,
            "trained_on": str(INPUT_CSV.name),
            "random_state": RANDOM_STATE,
            "config": canonical_key,
            "ndvi_corrected": ndvi_corrected,
            "caveat": (
                ""
                if ndvi_corrected
                else "NDVI feature looks uncorrected (raw-DN artifact). "
                "Predictions inherit that bias."
            ),
        },
        MODEL_PATH,
    )
    print(f"\nSaved canonical model ({canonical_key}) -> {MODEL_PATH.relative_to(MODULE_DIR)}")

    # ---------------------------------- plots ------------------------------
    y_pred = canonical_model.predict(
        df.loc[canonical_test_idx, BASE_FEATURES].to_numpy()
    )
    y_obs = y[canonical_test_idx]
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y_obs, y_pred, s=6, alpha=0.3, edgecolors="none")
    lims = [min(y_obs.min(), y_pred.min()), max(y_obs.max(), y_pred.max())]
    ax.plot(lims, lims, "r--", linewidth=1, label="1:1")
    ax.set_xlabel("Observed LST (C)")
    ax.set_ylabel("Predicted LST (C)")
    ax.set_title("RandomForest, base features, random 80/20 hold-out")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "pred_vs_actual.png", dpi=130)
    plt.close(fig)

    importances = pd.Series(
        canonical_model.feature_importances_, index=canonical_names
    ).sort_values()
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(importances.index, importances.to_numpy(), color="#d7191c")
    ax.set_xlabel("Feature importance (impurity reduction)")
    ax.set_title("RandomForest feature importance - target LST")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "feature_importances.png", dpi=130)
    plt.close(fig)

    # --------------------------------- reports -----------------------------
    (RESULTS_DIR / "metrics.json").write_text(
        json.dumps(
            {
                "target": TARGET,
                "random_state": RANDOM_STATE,
                "canonical_model": canonical_key,
                "ndvi_corrected": ndvi_corrected,
                "results": rows,
                "feature_importances": importances.to_dict(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Regression metrics",
        "",
        f"Target: **{TARGET}** (degrees C). Seed: `{RANDOM_STATE}`. "
        f"Rows: {len(df):,}. Test fraction: {TEST_FRACTION:.0%}.",
        "",
        (
            "> NDVI comes from the corrected surface-reflectance export."
            if ndvi_corrected
            else "> NDVI looks uncorrected. Metrics are internally valid but the "
            "NDVI-temperature relationship is attenuated."
        ),
        "",
        "> Quote the **spatial_block** R2, not the random_80_20 one. Adjacent "
        "100 m cells are near-duplicates, so a random split leaks most test "
        "answers through their neighbours and flatters the model badly.",
        "",
        "| Split | Features | Model | RMSE (C) | MAE (C) | R2 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['split']} | {r['features']} | {r['model']} | "
            f"{r['rmse']:.4f} | {r['mae']:.4f} | {r['r2']:.4f} |"
        )
    lines += [
        "",
        "## Feature importances (canonical model)",
        "",
        "| Feature | Importance |",
        "|---|---|",
    ]
    for name, val in importances.sort_values(ascending=False).items():
        lines.append(f"| {name} | {val:.4f} |")
    (RESULTS_DIR / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote metrics -> Results/metrics.md, Results/metrics.json")
    print("Wrote plots   -> Results/pred_vs_actual.png, Results/feature_importances.png")


if __name__ == "__main__":
    main()
