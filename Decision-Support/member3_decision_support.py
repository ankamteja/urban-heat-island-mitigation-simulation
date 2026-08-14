"""
<<<<<<< HEAD
Member 3 - Decision Support
Urban Heat Island cooling-intervention recommender for Guwahati.

Pipeline:
  1. Load real grid data from Member 1 (Guwahati_Urban_Heat_Dataset.csv), with a
     synthetic fallback (USE_SYNTHETIC = True) so you're never blocked
     - extract lat/lon centroids from the .geo column (don't wait on their fix)
     - derive a PROXY land-cover from NDVI/LST until Member 1 adds real WorldCover data
  2. Apply hard suitability rules per intervention type (no ponds on highways, etc.)
  3. Score cooling benefit vs cost -> cooling_per_rupee
  4. Greedily rank grid cells (highest cooling_per_rupee first)
  5. Export recommendation.csv (per-cell best option), excluded.csv (cells with no
     valid intervention) and ranking.csv (priority-ordered list)

Input and output paths are resolved relative to this file, so the script runs from
anywhere in the repo - nothing to hand-edit.

STATUS NOTE (2026-08-07): real dataset has no land_cover column yet (per Member 1/2
audit). This script uses a documented NDVI/LST-based PROXY so the pipeline runs
end-to-end today. Swap in real land_cover the moment Member 1 exports it (their
audit snippet D) - just change USE_PROXY_LANDCOVER to False, everything else
downstream is unchanged.
"""

import json
from pathlib import Path

import numpy as np
=======
Decision Support (v3)
Urban Heat Island priority ranking for Guwahati - now on real land cover.

WHY THIS VERSION EXISTS:
v2 consumed the ML module's tiered.csv, which had real per-cell cost but no
real land-cover suitability filtering (land cover didn't exist upstream yet).
The satellite processing pipeline has since been re-run with the NDVI
rescale fix applied - the committed dataset now has genuine ESA WorldCover
land-cover codes, corrected NDVI (max 0.78, previously capped at 0.39), and
real Latitude/Longitude. That finally makes the suitability filter
meaningful instead of a documented no-op.

tiered.csv is NOT used here. Its tiers and actions were computed against the
old, uncorrected NDVI - Heat_Risk quartile thresholds shifted completely
after the fix (old: 0.006 / 0.241, new: -0.325 / 0.040), so every tier and
action assignment in it is now stale. This module computes tiering directly
from the corrected dataset instead of waiting on a rerun of that pipeline,
since it doesn't depend on anything else changing.

INPUT PATH: resolves relative to this file's own location in the repo
(../Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv),
not a hardcoded absolute path - runs correctly from any clean clone, verified
against the actual committed repo structure.

PIPELINE:
  1. Load dataset.csv (grid_id, LST, NDVI, Heat_Risk, LandCover, Latitude,
     Longitude, NDBI, Vegetation)
  2. Map real ESA WorldCover land-cover codes to suitability categories
  3. Apply hard suitability rules (never-touch water/wetland; roof-type
     interventions only on built-up; ground interventions only on open land)
  4. Tier by Heat_Risk quartile (High/Medium/Low), same convention as
     the ML module's original approach, recomputed on corrected data
  5. Score cooling_c / cost_estimate using real cell-area-based cost
  6. Greedy, budget-capped ranking
  7. Export recommendation.csv, ranking.csv, excluded.csv

KNOWN LIMITATION, STATED HONESTLY:
ESA WorldCover has no dedicated road class - roads are folded into the
generic "built-up" category alongside buildings. This module cannot fully
guarantee "no interventions on roads" as a result. The mitigation: ground-
level interventions (tree cover, park) are restricted to open-land classes
only and never placed on built-up cells; built-up cells are only ever
assigned roof-type interventions (cool roof), which are moot rather than
harmful if a given built-up cell actually turns out to be a road. This is
the same defensive principle used in earlier revisions, now applied to real
data instead of a coarse NDVI proxy.
"""

import os
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
import pandas as pd

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
<<<<<<< HEAD
USE_SYNTHETIC = False
USE_PROXY_LANDCOVER = True   # flip to False once Member 1 adds real land_cover column
GRID_CELL_AREA_M2 = 100 * 100
=======
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_CSV = os.path.join(
    SCRIPT_DIR, "..", "Remote Sensing & Data Engineering", "Dataset",
    "Guwahati_Urban_Heat_Dataset.csv"
)
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

# Grid cells are ~100m defined in degrees, not a projected CRS, so they are
# not exactly square in metres. Verified in the Remote Sensing audit:
# 0.00089832 deg square -> 89.8m x 99.3m at this latitude = ~8,918 sq m.
# Matches cell_area_m2 previously computed by the ML module's own export.
CELL_AREA_M2 = 8918.0

# Per-square-metre unit rates (INR), same rates the ML module used - these
# don't depend on NDVI or land cover, so they remain valid unchanged.
RATE_COOL_ROOF = 60.0
RATE_TREE_COVER = 37.5
RATE_GREEN_PARK = 25.0

# Cooling estimates (deg C) - stated engineering assumptions, not measured
# or fitted for Guwahati. Unchanged from all earlier revisions.
COOLING_COOL_ROOF = 1.0
COOLING_TREE_COVER = 0.8
COOLING_GREEN_PARK = 2.0

BUDGET_RUPEES = 100_000_000  # INR 10 crore demo default

# ------------------------------------------------------------------
# PATHS (resolved relative to this file, so the script runs from anywhere)
# Same convention as Machine Learning & Prediction/scripts/preprocess.py.
# This file sits directly in Decision-Support/, so .parent IS the module dir.
# ------------------------------------------------------------------
MODULE_DIR = Path(__file__).resolve().parent
REPO_DIR = MODULE_DIR.parent
SOURCE_CSV = (
    REPO_DIR
    / "Remote Sensing & Data Engineering"
    / "Dataset"
    / "Guwahati_Urban_Heat_Dataset.csv"
)   # Member 1's real export

RECOMMENDATION_CSV = MODULE_DIR / "recommendation.csv"
EXCLUDED_CSV = MODULE_DIR / "excluded.csv"
RANKING_CSV = MODULE_DIR / "ranking.csv"

# ------------------------------------------------------------------
# STEP 0: LOAD DATA
# ------------------------------------------------------------------
df = pd.read_csv(DATASET_CSV)
df = df.rename(columns={"Latitude": "lat", "Longitude": "lon"})

<<<<<<< HEAD

def proxy_land_cover(row, ndvi_q1, ndvi_q3):
    """
    Stand-in classifier until real WorldCover land_cover lands (Member 1 audit item D).
    Uses QUANTILE thresholds (top/bottom 25% of this dataset's own NDVI distribution)
    instead of fixed values - this stays correct whether NDVI is the current
    compressed/buggy version (audit item #3) or Member 1's eventual fixed version,
    since it always splits relative to what's actually in the data.
    Cannot distinguish road/building/parking (all read as 'low NDVI' from satellite
    alone) - that's exactly why pond/park placement waits for real land cover.
    """
    ndvi = row["ndvi"]
    if ndvi >= ndvi_q3:
        return "vegetated"
    elif ndvi >= ndvi_q1:
        return "moderate"
    else:
        return "bare_or_built_hot"


def load_data():
    if USE_SYNTHETIC:
        rng = np.random.default_rng(42)
        n = 400
        land_covers = rng.choice(
            ["residential", "vacant", "road", "highway", "water", "wetland",
             "hillslope", "building_dense", "park"],
            size=n,
            p=[0.28, 0.16, 0.10, 0.06, 0.04, 0.06, 0.10, 0.14, 0.06],
        )
        lat0, lon0 = 26.144, 91.736
        df = pd.DataFrame({
            "grid_id": [f"g{i:04d}" for i in range(n)],
            "lat": lat0 + rng.normal(0, 0.03, n),
            "lon": lon0 + rng.normal(0, 0.03, n),
            "land_cover": land_covers,
            "ndvi": rng.uniform(-0.1, 0.8, n),
            "predicted_temp": rng.normal(38, 3, n),
        })
        return df

    # Fail loudly and explanatorily rather than letting pandas raise a bare
    # FileNotFoundError on a path the reader has no context for.
    if not SOURCE_CSV.exists():
        raise FileNotFoundError(
            f"Source dataset not found: {SOURCE_CSV}\n"
            "Expected the Remote Sensing & Data Engineering module's exported CSV.\n"
            "Set USE_SYNTHETIC = True to run this module on synthetic data instead."
        )

    df = pd.read_csv(SOURCE_CSV)
    print(f"Loaded {len(df)} rows from {SOURCE_CSV}")
    df = df.join(df[".geo"].apply(extract_centroid))
    df = df.rename(columns={"LST": "predicted_temp", "NDVI": "ndvi"})

    if USE_PROXY_LANDCOVER:
        q1, q3 = df["ndvi"].quantile([0.25, 0.75])
        print(f"Proxy NDVI thresholds (this run): bottom 25% < {q1:.3f}, top 25% >= {q3:.3f}")
        df["land_cover"] = df.apply(proxy_land_cover, axis=1, ndvi_q1=q1, ndvi_q3=q3)
    else:
        if "LandCover" in df.columns:
            df = df.rename(columns={"LandCover": "land_cover"})

    return df


df = load_data()
print(f"Loaded {len(df)} grid cells")
print(f"Land cover source: {'PROXY (NDVI/LST-based)' if USE_PROXY_LANDCOVER else 'real'}")
print(df["land_cover"].value_counts())

# ------------------------------------------------------------------
# STEP 1: INTERVENTION CATALOG - cost & cooling assumptions
# Numbers are placeholder engineering estimates for a hackathon demo.
# The cooling_c degrees-Celsius values are this module's own assumptions and are
# not superseded by anything - state clearly in your report/pitch that they are
# assumptions, not measured field data. That's honest and judges respect it.
# The rupee costs are a different matter; see the block immediately below.
#
# SUPERSEDED COST MODEL - DO NOT QUOTE THESE RUPEE FIGURES TO ANYONE
#
# The cost_per_cell values below are placeholder FLAT PER-CELL estimates. They
# are retained here for one reason only: this module's internal
# cooling_per_rupee ranking, which depends on the RATIOS between them. Do not
# change the numbers - changing any of them reorders the greedy ranking.
#
# A cross-module audit found these disagree with the Machine Learning module's
# AREA-BASED cost model by 18-67x for the same intervention. The project has
# decided that the ML module's model is the single source of truth for any
# user-facing figure: see COST_HEURISTICS in
#   Machine Learning & Prediction/scripts/tier_and_recommend.py
# (INR per m2 x coverage fraction x actual cell area).
#
# So: for any reported, displayed, or pitched cost, use COST_HEURISTICS. The
# two models must NEVER be quoted side by side - they are different units on
# different bases, and presenting both invites a false comparison.
=======
print(f"Loaded {len(df)} grid cells from dataset.csv")
print(f"NDVI range: {df['NDVI'].min():.3f} to {df['NDVI'].max():.3f} "
      f"(confirms corrected data - buggy version capped at 0.386)")

# ------------------------------------------------------------------
# STEP 1: MAP REAL LAND COVER TO SUITABILITY CATEGORIES
# ESA WorldCover v200 class codes:
#   10 tree cover, 20 shrubland, 30 grassland, 40 cropland, 50 built-up,
#   60 bare/sparse vegetation, 80 water, 90 herbaceous wetland
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
# ------------------------------------------------------------------
LANDCOVER_LABELS = {
    10: "tree_cover", 20: "shrubland", 30: "grassland", 40: "cropland",
    50: "built_up", 60: "bare_sparse", 70: "snow_ice", 80: "water",
    90: "wetland", 95: "mangroves", 100: "moss_lichen",
}
df["land_cover"] = df["LandCover"].map(LANDCOVER_LABELS).fillna("unknown")

print(f"\nLand cover distribution:\n{df['land_cover'].value_counts()}")

NEVER_TOUCH = ["water", "wetland"]
ALREADY_GREEN = ["tree_cover"]
# built_up: roof-type only (could be a road, WorldCover has no road class - see module docstring)
ROOF_ELIGIBLE = ["built_up"]
# open land: ground-type only, never built_up
GROUND_ELIGIBLE = ["bare_sparse", "grassland", "cropland"]

# ------------------------------------------------------------------
# STEP 2: TIER BY HEAT_RISK (recomputed on corrected data)
# ------------------------------------------------------------------
q1, q3 = df["Heat_Risk"].quantile([0.25, 0.75])
print(f"\nHeat_Risk quartiles (corrected data): Low <{q1:.4f}, High >={q3:.4f}")


def assign_tier(heat_risk):
    if heat_risk >= q3:
        return "High"
    elif heat_risk <= q1:
        return "Low"
    return "Medium"


df["priority"] = df["Heat_Risk"].apply(assign_tier)

# ------------------------------------------------------------------
# STEP 3: SUITABILITY FILTER + ACTION ASSIGNMENT
# ------------------------------------------------------------------
def assign_action(row):
    lc = row["land_cover"]
    tier = row["priority"]

    if lc in NEVER_TOUCH:
        return None, "excluded (never-touch land cover: water/wetland)"
    if lc in ALREADY_GREEN:
        return None, "already vegetated (tree cover) - no action needed"
    if tier == "Low":
        return None, "Low priority - no action needed"

    if lc in ROOF_ELIGIBLE:
        return "Cool roof", None
    if lc in GROUND_ELIGIBLE:
        # High-priority open land gets the larger intervention (park);
        # Medium-priority open land gets the lighter one (tree cover)
        return ("Green park" if tier == "High" else "Tree cover"), None

    return None, f"excluded (unclassified land cover: {lc})"


actions = df.apply(assign_action, axis=1, result_type="expand")
df["recommended_action"] = actions[0]
df["exclusion_reason"] = actions[1]

ACTION_SPEC = {
    "Cool roof": (RATE_COOL_ROOF, COOLING_COOL_ROOF),
    "Tree cover": (RATE_TREE_COVER, COOLING_TREE_COVER),
    "Green park": (RATE_GREEN_PARK, COOLING_GREEN_PARK),
}
df["cost_estimate"] = df["recommended_action"].map(
    lambda a: ACTION_SPEC[a][0] * CELL_AREA_M2 if a in ACTION_SPEC else None
)
df["cooling_c"] = df["recommended_action"].map(
    lambda a: ACTION_SPEC[a][1] if a in ACTION_SPEC else None
)

excluded = df[df["recommended_action"].isna()].copy()
recommendation = df[df["recommended_action"].notna()].copy()

print(f"\nExcluded: {len(excluded)} cells")
print(excluded["exclusion_reason"].value_counts())
print(f"\nActionable cells: {len(recommendation)}")
print(recommendation["recommended_action"].value_counts())

# ------------------------------------------------------------------
# STEP 4: SCORE + GREEDY BUDGET-CAPPED RANKING
# ------------------------------------------------------------------
recommendation["cooling_per_rupee"] = (
    recommendation["cooling_c"] / recommendation["cost_estimate"]
)

ranking = recommendation.sort_values("cooling_per_rupee", ascending=False).reset_index(drop=True)
ranking["rank"] = ranking.index + 1
ranking["cumulative_cost"] = ranking["cost_estimate"].cumsum()
ranking["within_budget"] = ranking["cumulative_cost"] <= BUDGET_RUPEES

n_selected = ranking["within_budget"].sum()
print(f"\nBudget INR {BUDGET_RUPEES:,}: funds top {n_selected} of {len(ranking)} actionable cells")
print(ranking.loc[ranking["within_budget"], "recommended_action"].value_counts())

# ------------------------------------------------------------------
# STEP 5: EXPORT DELIVERABLES
# ------------------------------------------------------------------
<<<<<<< HEAD
recommendation_cols = ["grid_id", "lat", "lon", "land_cover", "predicted_temp",
                        "intervention", "cost_rupees", "cooling_c"]
recommendation.to_csv(RECOMMENDATION_CSV, index=False, columns=recommendation_cols)

excluded_cols = ["grid_id", "lat", "lon", "land_cover", "predicted_temp", "exclusion_reason"]
excluded.to_csv(EXCLUDED_CSV, index=False, columns=excluded_cols)
=======
recommendation_cols = ["grid_id", "lat", "lon", "land_cover", "priority", "LST",
                        "NDVI", "recommended_action", "cost_estimate", "cooling_c",
                        "cooling_per_rupee"]
recommendation.to_csv("recommendation.csv", index=False, columns=recommendation_cols)

excluded_cols = ["grid_id", "lat", "lon", "land_cover", "priority", "LST",
                  "exclusion_reason"]
excluded.to_csv("excluded.csv", index=False, columns=excluded_cols)
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

ranking_cols = ["rank", "grid_id", "lat", "lon", "recommended_action", "cost_estimate",
                 "cooling_c", "cooling_per_rupee", "cumulative_cost", "within_budget"]
<<<<<<< HEAD
ranking.to_csv(RANKING_CSV, index=False, columns=[c for c in ranking_cols if c in ranking.columns])

# Outputs land next to this script (MODULE_DIR), not in whatever directory you
# happened to launch from - print the resolved paths so there's no guessing.
print("\nSaved outputs:")
print(f"  {RECOMMENDATION_CSV}")
print(f"  {EXCLUDED_CSV}")
print(f"  {RANKING_CSV}")
print("\nTop 5 priority interventions:")
print(ranking[["rank", "grid_id", "intervention", "cost_rupees", "cooling_c", "cooling_per_rupee"]].head())
=======
ranking.to_csv("ranking.csv", index=False, columns=ranking_cols)

print("\nSaved recommendation.csv, ranking.csv, excluded.csv")
print("\nTop 5 priority cells:")
print(ranking[["rank", "grid_id", "recommended_action", "cost_estimate",
                "cooling_c", "cooling_per_rupee"]].head())
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
