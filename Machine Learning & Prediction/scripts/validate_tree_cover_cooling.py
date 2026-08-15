"""Describe the observed LST contrast between tree cover and nearby built-up cells.

This is a reproducible *sanity check*, not an intervention-effect estimate.
The committed Landsat scene was not collected before and after planting trees,
so it cannot validate the 0.8 C planning assumption used by the dashboard.
It can, however, test the much smaller claim that cells ESA WorldCover labels
as tree cover are cooler than nearby built-up cells in this scene.

Method
------
For every tree-cover cell, find up to eight built-up candidates within 500 m.
Sort all candidate pairs by distance and greedily retain one-to-one nearest
pairs. The reported contrast is built-up LST minus tree-cover LST. A fixed-seed
bootstrap of matched pairs supplies a descriptive interval only; spatial
dependence and land-cover confounding make it unsuitable as a causal interval.

Run from the repository root:
    python3 "Machine Learning & Prediction/scripts/validate_tree_cover_cooling.py"

The script writes Results/tree_cover_cooling_validation.{json,md}. Commit both
outputs whenever the source dataset is refreshed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent
RESULTS_DIR = MODULE_DIR / "Results"

TREE_COVER_CODE = 10
BUILT_UP_CODE = 50
MATCH_RADIUS_M = 500.0
CANDIDATES_PER_TREE_CELL = 8
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260815
METRES_PER_DEG_LAT = 110_574.0
METRES_PER_DEG_LON_EQUATOR = 111_320.0


def to_local_metres(frame: pd.DataFrame, origin_lat: float) -> np.ndarray:
    """Project latitude/longitude to a local equirectangular metre grid."""
    return np.column_stack(
        [
            frame["Longitude"].to_numpy() * METRES_PER_DEG_LON_EQUATOR * np.cos(np.radians(origin_lat)),
            frame["Latitude"].to_numpy() * METRES_PER_DEG_LAT,
        ]
    )


def match_tree_to_built_up(dataset: pd.DataFrame) -> pd.DataFrame:
    """Return deterministic, one-to-one tree-cover/built-up matches."""
    tree = dataset.loc[dataset["LandCover"] == TREE_COVER_CODE].copy()
    built = dataset.loc[dataset["LandCover"] == BUILT_UP_CODE].copy()
    if tree.empty or built.empty:
        raise ValueError("Need both tree-cover and built-up cells for the contrast check.")

    origin_lat = float(dataset["Latitude"].mean())
    tree_xy = to_local_metres(tree, origin_lat)
    built_xy = to_local_metres(built, origin_lat)
    distances, neighbours = cKDTree(built_xy).query(
        tree_xy,
        k=min(CANDIDATES_PER_TREE_CELL, len(built)),
        distance_upper_bound=MATCH_RADIUS_M,
    )
    distances = np.atleast_2d(distances)
    neighbours = np.atleast_2d(neighbours)
    if distances.shape[0] != len(tree):
        distances, neighbours = distances.T, neighbours.T

    candidates: list[tuple[float, int, int]] = []
    for tree_at, (row_distances, row_neighbours) in enumerate(zip(distances, neighbours, strict=True)):
        for distance, built_at in zip(row_distances, row_neighbours, strict=True):
            if np.isfinite(distance) and built_at < len(built):
                candidates.append((float(distance), tree_at, int(built_at)))

    used_tree: set[int] = set()
    used_built: set[int] = set()
    pairs: list[tuple[float, int, int]] = []
    for distance, tree_at, built_at in sorted(candidates):
        if tree_at not in used_tree and built_at not in used_built:
            pairs.append((distance, tree_at, built_at))
            used_tree.add(tree_at)
            used_built.add(built_at)

    if not pairs:
        raise ValueError(f"No tree/built-up matches within {MATCH_RADIUS_M:.0f} m.")

    pair_distances, tree_positions, built_positions = zip(*pairs, strict=True)
    tree_matched = tree.iloc[list(tree_positions)].reset_index(drop=True)
    built_matched = built.iloc[list(built_positions)].reset_index(drop=True)
    return pd.DataFrame(
        {
            "tree_grid_id": tree_matched["grid_id"].astype(str),
            "built_up_grid_id": built_matched["grid_id"].astype(str),
            "distance_m": pair_distances,
            "tree_lst_c": tree_matched["LST"].to_numpy(),
            "built_up_lst_c": built_matched["LST"].to_numpy(),
        }
    ).assign(contrast_c=lambda d: d.built_up_lst_c - d.tree_lst_c)


def bootstrap_interval(values: np.ndarray) -> tuple[float, float]:
    """Return the fixed-seed percentile bootstrap interval for the mean."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = rng.integers(0, len(values), size=(BOOTSTRAP_REPLICATES, len(values)))
    means = values[samples].mean(axis=1)
    return tuple(float(v) for v in np.quantile(means, [0.025, 0.975]))


def summarise(matches: pd.DataFrame, source: Path) -> dict[str, float | int | str]:
    """Build machine-readable output; keep rounding for presentation only."""
    contrast = matches["contrast_c"].to_numpy()
    interval_low, interval_high = bootstrap_interval(contrast)
    return {
        "source_dataset": str(source.relative_to(REPO_DIR)),
        "method": "one-to-one greedy nearest-neighbour match",
        "tree_cover_code": TREE_COVER_CODE,
        "built_up_code": BUILT_UP_CODE,
        "match_radius_m": MATCH_RADIUS_M,
        "candidate_built_up_cells_per_tree": CANDIDATES_PER_TREE_CELL,
        "matched_pairs": int(len(matches)),
        "mean_distance_m": float(matches["distance_m"].mean()),
        "max_distance_m": float(matches["distance_m"].max()),
        "mean_tree_cover_lst_c": float(matches["tree_lst_c"].mean()),
        "mean_built_up_lst_c": float(matches["built_up_lst_c"].mean()),
        "mean_observed_contrast_c": float(contrast.mean()),
        "median_observed_contrast_c": float(np.median(contrast)),
        "bootstrap_95_interval_c": [interval_low, interval_high],
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
    }


def render_markdown(summary: dict[str, float | int | str]) -> str:
    """Render the committed human-readable result from the JSON summary."""
    low, high = summary["bootstrap_95_interval_c"]
    return f"""# Tree-cover LST contrast check

Generated by `scripts/validate_tree_cover_cooling.py` from
`{summary['source_dataset']}`.

| Quantity | Result |
|---|---:|
| Matched tree-cover / built-up pairs | {summary['matched_pairs']:,} |
| Match radius | ≤ {summary['match_radius_m']:.0f} m |
| Mean pair distance | {summary['mean_distance_m']:.1f} m |
| Maximum pair distance | {summary['max_distance_m']:.1f} m |
| Mean tree-cover LST | {summary['mean_tree_cover_lst_c']:.2f} °C |
| Mean built-up LST | {summary['mean_built_up_lst_c']:.2f} °C |
| Mean observed contrast (built-up − tree cover) | **{summary['mean_observed_contrast_c']:.2f} °C** |
| Median observed contrast | {summary['median_observed_contrast_c']:.2f} °C |
| Descriptive bootstrap 95% interval for mean contrast | {low:.2f} to {high:.2f} °C |

## Interpretation

In this Landsat scene, matched cells classified as tree cover are cooler than
nearby matched cells classified as built-up by the reported contrast. This is a
useful directional check on the sign of a tree-cover cooling claim.

It is **not** an estimate or validation of the dashboard's 0.8 °C tree-planting
scenario: the data are a single cross-sectional satellite scene, not a
before/after intervention study. Existing canopy, surface material, shade,
building density, terrain and imperfect land-cover registration can all explain
part of the difference. The contrast says nothing about cool roofs or parks.

See [`docs/10-tree-cover-check.md`](../../docs/10-tree-cover-check.md) for the
method and [the limitations](../../docs/08-limitations.md) for how this result
may and may not be used.
"""


def main() -> None:
    import sys

    sys.path.insert(0, str(REPO_DIR / "shared"))
    import uhi_shared as shared

    source = shared.source_dataset_path()
    dataset = pd.read_csv(source)
    matches = match_tree_to_built_up(dataset)
    summary = summarise(matches, source)

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "tree_cover_cooling_validation.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (RESULTS_DIR / "tree_cover_cooling_validation.md").write_text(
        render_markdown(summary), encoding="utf-8"
    )
    print(render_markdown(summary))


if __name__ == "__main__":
    main()
