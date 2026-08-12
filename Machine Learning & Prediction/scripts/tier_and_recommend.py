"""
Step 3 - Priority tiering and mitigation recommendations.

There is no labelled ground truth anywhere in this project for "priority" or
"recommended action", so this step is deliberately NOT a supervised classifier
pretending to have learned them. It is an explicit, auditable rule engine over
Heat_Risk and NDVI. Every threshold and unit cost is a named constant below and
is reproduced in README sections 4 and 5.

Input : Results/preprocessed.csv
Output: Results/tiered.csv
        Results/priority_map.png
        Results/tiering_summary.md

Run:  python scripts/tier_and_recommend.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import shape

# ---------------------------------------------------------------------------
# Rule 1 - priority tiers: quantile bins on Heat_Risk.
#
# Quantiles, not absolute Heat_Risk cutoffs, because Heat_Risk is biased high
# by the uncorrected NDVI (SPEC_AUDIT #3) - an absolute threshold would be
# calibrated to a biased scale. Quantiles at least keep the tiers as *relative*
# ranks within this city.
#
# Caveat that survives the quantile trick: a perfectly uniform bias would
# cancel out of a ranking, but this one does not. The NDVI error is
# brightness-dependent, so it compresses the NDVI term's variance unevenly and
# leaves Heat_Risk over-weighted toward LST. Tier boundaries are therefore
# approximate even as ranks.
# ---------------------------------------------------------------------------
HIGH_QUANTILE = 0.75  # top 25% of Heat_Risk -> High
LOW_QUANTILE = 0.25  # bottom 25% of Heat_Risk -> Low
#                      the middle 50% -> Medium

# ---------------------------------------------------------------------------
# Rule 2 - vegetation split for the action table.
#
# The literature threshold for "vegetated" is NDVI ~0.3, but the uncorrected
# NDVI here has a p95 of only ~0.295, so an absolute 0.3 would label virtually
# the whole city as sparse and collapse the decision table. We therefore split
# at the dataset MEDIAN - a within-city relative measure. Once Fix A lands
# upstream and NDVI is physically correct, switch this to an absolute 0.3.
# ---------------------------------------------------------------------------
VEGETATION_SPLIT_QUANTILE = 0.50

# ---------------------------------------------------------------------------
# Rule 3 - decision table, keyed on (priority, vegetation class).
#
# Action names are fixed by the dashboard: frontend/js/popup.js renders
# recommended_action verbatim, and only these four values are expected.
# ---------------------------------------------------------------------------
ACTION_TABLE: dict[tuple[str, str], str] = {
    ("High", "sparse"): "Tree cover",  # hot + little vegetation -> plant
    ("High", "vegetated"): "Cool roof",  # hot but already green -> treat surfaces
    ("Medium", "sparse"): "Green park",
    ("Medium", "vegetated"): "Green park",
    ("Low", "sparse"): "None",
    ("Low", "vegetated"): "None",
}

# ---------------------------------------------------------------------------
# Rule 4 - cost heuristics.
#
# THESE ARE PLANNING PLACEHOLDERS, NOT FITTED OR PROCURED COSTS. They are
# order-of-magnitude figures chosen so the dashboard can rank cells by relative
# investment; they have no tender or survey behind them. Replace with real
# municipal unit rates before any figure here informs a budget.
#
# coverage_fraction = share of the ~8,900 m2 cell actually treated. Treating
# 100% of a cell is not physically realistic (roads, buildings, water), so each
# action carries its own plausible coverage.
# ---------------------------------------------------------------------------
COST_HEURISTICS: dict[str, dict[str, float]] = {
    "Tree cover": {"inr_per_m2": 150.0, "coverage_fraction": 0.25},
    "Cool roof": {"inr_per_m2": 400.0, "coverage_fraction": 0.15},
    "Green park": {"inr_per_m2": 250.0, "coverage_fraction": 0.10},
    "None": {"inr_per_m2": 0.0, "coverage_fraction": 0.0},
}

# Degrees -> metres for cell area. The .geo polygons are axis-aligned
# rectangles in EPSG:4326, so a local equirectangular conversion is exact for
# their width/height (see Remote Sensing SPEC_AUDIT item #6: ~89.8 m x 99.3 m).
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON_EQUATOR = 111_320.0

MODULE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = MODULE_DIR / "Results"
INPUT_CSV = RESULTS_DIR / "preprocessed.csv"
OUTPUT_CSV = RESULTS_DIR / "tiered.csv"


def cell_area_m2(geo_json_str: str) -> float:
    """Metric area of one grid cell, from its polygon bounds."""
    poly = shape(json.loads(geo_json_str))
    min_x, min_y, max_x, max_y = poly.bounds
    mid_lat_rad = np.radians((min_y + max_y) / 2.0)
    width_m = (max_x - min_x) * M_PER_DEG_LON_EQUATOR * np.cos(mid_lat_rad)
    height_m = (max_y - min_y) * M_PER_DEG_LAT
    return float(width_m * height_m)


def assign_priority(heat_risk: pd.Series) -> tuple[pd.Series, float, float]:
    low_cut = float(heat_risk.quantile(LOW_QUANTILE))
    high_cut = float(heat_risk.quantile(HIGH_QUANTILE))
    priority = pd.Series("Medium", index=heat_risk.index, dtype="object")
    priority[heat_risk >= high_cut] = "High"
    priority[heat_risk <= low_cut] = "Low"
    return priority, low_cut, high_cut


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found - run scripts/preprocess.py first."
        )
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df):,} preprocessed rows")
    print(
        "WARNING: tiers derive from Heat_Risk, which is biased high by the "
        "uncorrected NDVI (SPEC_AUDIT #3). Treat tiers as indicative ranks."
    )

    # --- priority -----------------------------------------------------------
    df["priority"], low_cut, high_cut = assign_priority(df["Heat_Risk"])
    print(
        f"Heat_Risk cutoffs: Low <= {low_cut:.6f} < Medium < "
        f"{high_cut:.6f} <= High"
    )

    # --- vegetation class ---------------------------------------------------
    veg_split = float(df["NDVI"].quantile(VEGETATION_SPLIT_QUANTILE))
    df["vegetation_class"] = np.where(df["NDVI"] < veg_split, "sparse", "vegetated")
    print(f"NDVI vegetation split (median): {veg_split:.6f}")

    # --- action -------------------------------------------------------------
    df["recommended_action"] = [
        ACTION_TABLE[(p, v)]
        for p, v in zip(df["priority"], df["vegetation_class"], strict=True)
    ]

    # --- cost ---------------------------------------------------------------
    df["cell_area_m2"] = [cell_area_m2(g) for g in df["geo_json"]]
    rates = df["recommended_action"].map(lambda a: COST_HEURISTICS[a]["inr_per_m2"])
    coverage = df["recommended_action"].map(
        lambda a: COST_HEURISTICS[a]["coverage_fraction"]
    )
    df["cost_estimate"] = (df["cell_area_m2"] * rates * coverage).round().astype("int64")

    print(
        f"Cell area: mean {df['cell_area_m2'].mean():,.0f} m2 "
        f"(min {df['cell_area_m2'].min():,.0f}, max {df['cell_area_m2'].max():,.0f})"
    )

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(df):,} rows -> {OUTPUT_CSV.relative_to(MODULE_DIR)}")

    # --- summary ------------------------------------------------------------
    counts = df.groupby(["priority", "recommended_action"], as_index=False).agg(
        cells=("grid_id", "size"),
        total_cost_inr=("cost_estimate", "sum"),
        mean_lst=("LST", "mean"),
        mean_ndvi=("NDVI", "mean"),
    )
    print("\n" + counts.to_string(index=False))
    print(f"\nTotal notional programme cost: INR {df['cost_estimate'].sum():,}")

    lines = [
        "# Tiering and recommendation summary",
        "",
        "> Heat_Risk is biased high by the uncorrected NDVI "
        "(Remote Sensing SPEC_AUDIT #3). Tiers are indicative ranks, not "
        "calibrated risk levels. Costs are planning placeholders.",
        "",
        "## Thresholds actually applied",
        "",
        "| Rule | Value |",
        "|---|---|",
        f"| Heat_Risk q{LOW_QUANTILE:.2f} (Low boundary) | {low_cut:.6f} |",
        f"| Heat_Risk q{HIGH_QUANTILE:.2f} (High boundary) | {high_cut:.6f} |",
        f"| NDVI vegetation split (q{VEGETATION_SPLIT_QUANTILE:.2f}) | {veg_split:.6f} |",
        "",
        "## Outcome",
        "",
        "| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in counts.iterrows():
        lines.append(
            f"| {r['priority']} | {r['recommended_action']} | {r['cells']:,} | "
            f"{r['mean_lst']:.2f} | {r['mean_ndvi']:.3f} | {r['total_cost_inr']:,} |"
        )
    lines += [
        "",
        f"**Total notional programme cost: INR {df['cost_estimate'].sum():,}** "
        "(placeholder unit rates - see README section 5).",
    ]
    (RESULTS_DIR / "tiering_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    # --- map ----------------------------------------------------------------
    colours = {"High": "#d7191c", "Medium": "#fdae61", "Low": "#2c7bb6"}
    fig, ax = plt.subplots(figsize=(9, 6))
    for tier in ["Low", "Medium", "High"]:
        sub = df[df["priority"] == tier]
        ax.scatter(
            sub["Longitude"],
            sub["Latitude"],
            s=4,
            c=colours[tier],
            label=f"{tier} ({len(sub):,})",
            edgecolors="none",
        )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Guwahati mitigation priority tiers (uncorrected NDVI - indicative)")
    ax.legend(title="Priority", loc="upper right", markerscale=3)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "priority_map.png", dpi=130)
    plt.close(fig)
    print("Wrote Results/tiering_summary.md, Results/priority_map.png")


if __name__ == "__main__":
    main()
