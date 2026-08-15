"""
Decision Support (v4)
Urban Heat Island priority ranking for Guwahati, on real ESA WorldCover land cover.

WHAT CHANGED IN v4
------------------
v3 was correct in substance but could not run from a clean clone: it looked for
`Guwahati_Urban_Heat_Dataset.csv`, which had been renamed to `dataset.csv`.
It also carried its own private copies of the unit rates, the cooling
assumptions, the land-cover mapping and the suitability rules - the same
constants the Machine Learning module maintained separately.

That duplication was not harmless. The ML module's copy had no land-cover input
at all, so the dashboard it feeds recommended planting trees on 148 water and
wetland cells and building parks on 3,433 built-up cells, while this module -
with the correct rule - quietly produced the right answer into files nobody
rendered.

Every shared constant and the suitability rule itself now live in
`shared/constants.json` and `shared/uhi_shared.py`, imported by both modules.
This module's numbers are unchanged; it simply no longer owns them alone.

The script is also now importable: previously every statement ran at module
level, so merely importing it executed the pipeline and wrote three CSVs as a
side effect. That made it impossible to unit-test. See `tests/`.

PIPELINE
--------
  1. Load the Remote Sensing module's exported grid dataset
  2. Map ESA WorldCover codes to suitability categories
  3. Apply the shared suitability rule (never-touch water/wetland; roof
     interventions only on built-up; ground interventions only on open land)
  4. Tier by Heat_Risk quartile
  5. Score cooling_c and cost_estimate from the shared rate table
  6. Greedy, budget-capped ranking
  7. Export recommendation.csv, ranking.csv, excluded.csv

KNOWN LIMITATION, STATED HONESTLY
---------------------------------
ESA WorldCover has no dedicated road class - roads are folded into the generic
"built-up" category alongside buildings. This module cannot fully guarantee "no
interventions on roads". The mitigation: ground-level interventions are
restricted to open-land classes and never placed on built-up cells; built-up
cells are only ever assigned roof-type interventions, which are moot rather
than harmful if a given built-up cell turns out to be a road.

Run:  python member3_decision_support.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402  (path must be set before import)

# Grid cells are ~100 m defined in degrees, not a projected CRS, so they are not
# exactly square in metres. Verified in the Remote Sensing audit:
# 0.00089832 deg square -> 89.8 m x 99.3 m at this latitude = ~8,918 m2.
#
# The ML module computes each cell's area from its own polygon instead, which
# varies between 8,912 and 8,920 m2. The two therefore differ by well under
# 0.1% on any given cell - acceptable, and documented here so the discrepancy
# is not mistaken for a disagreement.
CELL_AREA_M2 = 8918.0

BUDGET_RUPEES = shared.CONSTANTS["budget_rupees"]

OUTPUT_RECOMMENDATION = SCRIPT_DIR / "recommendation.csv"
OUTPUT_EXCLUDED = SCRIPT_DIR / "excluded.csv"
OUTPUT_RANKING = SCRIPT_DIR / "ranking.csv"


def load_dataset() -> pd.DataFrame:
    """Load the grid dataset and rename coordinates to this module's convention."""
    path = shared.source_dataset_path()
    df = pd.read_csv(path)
    df = df.rename(columns={"Latitude": "lat", "Longitude": "lon"})

    required = {"grid_id", "LST", "NDVI", "Heat_Risk", "LandCover", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{path.name} is missing expected columns: {sorted(missing)}. "
            "LandCover comes from the corrected Earth Engine export."
        )

    print(f"Loaded {len(df):,} grid cells from {path.name}")
    ndvi_max = float(df["NDVI"].max())
    if shared.ndvi_looks_corrected(ndvi_max):
        print(f"NDVI range: {df['NDVI'].min():.3f} to {ndvi_max:.3f} (corrected export)")
    else:
        print(
            f"WARNING: NDVI max is only {ndvi_max:.3f} - this looks like the "
            "pre-fix raw-DN export. Heat_Risk is biased high."
        )
    return df


def add_land_cover(df: pd.DataFrame) -> pd.DataFrame:
    df["land_cover"] = df["LandCover"].map(shared.land_cover_label)
    print(f"\nLand cover distribution:\n{df['land_cover'].value_counts()}")
    return df


def assign_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """Heat_Risk quartile tiers, using the shared cut points."""
    q_low = shared.TIERING["low_quantile"]
    q_high = shared.TIERING["high_quantile"]
    low_cut, high_cut = df["Heat_Risk"].quantile([q_low, q_high])
    print(f"\nHeat_Risk quartiles: Low <= {low_cut:.4f}, High >= {high_cut:.4f}")

    def tier(heat_risk: float) -> str:
        if heat_risk >= high_cut:
            return "High"
        if heat_risk <= low_cut:
            return "Low"
        return "Medium"

    df["priority"] = df["Heat_Risk"].apply(tier)
    return df


def assign_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the shared suitability rule and cost/cooling lookups."""
    assigned = [
        shared.assign_action(lc, p)
        for lc, p in zip(df["land_cover"], df["priority"], strict=True)
    ]
    df["recommended_action"] = [a for a, _ in assigned]
    df["exclusion_reason"] = [r for _, r in assigned]

    actionable = df["recommended_action"] != "None"
    df["cost_estimate"] = [
        shared.action_cost(a, CELL_AREA_M2) if a != "None" else None
        for a in df["recommended_action"]
    ]
    df["cooling_c"] = [
        shared.action_cooling_c(a) if a != "None" else None
        for a in df["recommended_action"]
    ]

    # The safety property the suitability rule exists to guarantee. Asserted,
    # not assumed - it is invisible in aggregate output.
    unsafe = df[df["land_cover"].isin(shared.NEVER_TOUCH) & actionable]
    if len(unsafe):
        raise AssertionError(
            f"{len(unsafe)} never-touch cells were assigned an intervention"
        )
    return df


def rank_within_budget(recommendation: pd.DataFrame) -> pd.DataFrame:
    """Greedy ranking by cooling per rupee, cut off at the budget."""
    recommendation = recommendation.copy()
    recommendation["cooling_per_rupee"] = (
        recommendation["cooling_c"] / recommendation["cost_estimate"]
    )
    # Ties are the normal case here, not an edge case: cost uses a flat cell
    # area, so every cell sharing an action has an identical cooling_per_rupee -
    # all 3,494 cool-roof cells score exactly the same. pandas' default sort is
    # quicksort, which is not stable, so the order within a tie was arbitrary
    # and the committed ranking.csv failed to reproduce: 4,154 of 4,157 rows
    # moved between runs. CI caught it.
    #
    # A stable mergesort plus explicit tie-breaks makes the order a deterministic
    # function of the data alone, independent of row order or platform.
    #
    # LST descending is the tie-break that decides the funded set. Determinism
    # alone was not enough: with grid_id as the only tie-break the budget funded
    # the first 249 cool-roof cells in spatial scan order, whose mean temperature
    # was 28.69 C against 30.16 C for the 249 hottest - the shortlist left ~1.5 C
    # of mean heat unaddressed while claiming to be heat-prioritised. Sorting the
    # tie by temperature spends the same money on the hottest eligible cells.
    # grid_id stays as the final tie-break so the file still reproduces exactly.
    ranking = recommendation.sort_values(
        ["cooling_per_rupee", "LST", "grid_id"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    ranking["rank"] = ranking.index + 1
    ranking["cumulative_cost"] = ranking["cost_estimate"].cumsum()
    ranking["within_budget"] = ranking["cumulative_cost"] <= BUDGET_RUPEES
    return ranking


def main() -> None:
    df = load_dataset()
    df = add_land_cover(df)
    df = assign_tiers(df)
    df = assign_actions(df)

    excluded = df[df["recommended_action"] == "None"].copy()
    recommendation = df[df["recommended_action"] != "None"].copy()

    print(f"\nNo action: {len(excluded):,} cells")
    print(excluded["exclusion_reason"].value_counts())
    print(f"\nActionable cells: {len(recommendation):,}")
    print(recommendation["recommended_action"].value_counts())

    recommendation["cooling_per_rupee"] = (
        recommendation["cooling_c"] / recommendation["cost_estimate"]
    )

    ranking = rank_within_budget(recommendation)
    n_selected = int(ranking["within_budget"].sum())
    print(
        f"\nBudget INR {BUDGET_RUPEES:,}: funds top {n_selected:,} of "
        f"{len(ranking):,} actionable cells"
    )
    print(ranking.loc[ranking["within_budget"], "recommended_action"].value_counts())

    recommendation.to_csv(
        OUTPUT_RECOMMENDATION,
        index=False,
        columns=[
            "grid_id", "lat", "lon", "land_cover", "priority", "LST", "NDVI",
            "recommended_action", "cost_estimate", "cooling_c",
            "cooling_per_rupee",
        ],
    )
    excluded.to_csv(
        OUTPUT_EXCLUDED,
        index=False,
        columns=[
            "grid_id", "lat", "lon", "land_cover", "priority", "LST",
            "exclusion_reason",
        ],
    )
    ranking.to_csv(
        OUTPUT_RANKING,
        index=False,
        columns=[
            # LST rides along because it is now a sort key: without it in the
            # file the ranking cannot be re-derived from its own output, and
            # "why is this cell funded and that one not?" has no answer.
            "rank", "grid_id", "lat", "lon", "LST", "recommended_action",
            "cost_estimate", "cooling_c", "cooling_per_rupee",
            "cumulative_cost", "within_budget",
        ],
    )

    print(
        f"\nSaved {OUTPUT_RECOMMENDATION.name}, {OUTPUT_RANKING.name}, "
        f"{OUTPUT_EXCLUDED.name} in {SCRIPT_DIR}"
    )
    print("\nTop 5 priority cells:")
    print(
        ranking[
            ["rank", "grid_id", "recommended_action", "cost_estimate",
             "cooling_c", "cooling_per_rupee"]
        ].head()
    )


if __name__ == "__main__":
    main()
