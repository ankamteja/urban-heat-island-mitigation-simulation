"""
Member 3 - Decision Support
Urban Heat Island cooling-intervention recommender.

Pipeline:
  1. Load grid data (real, from Member 1/2, OR synthetic fallback so you're never blocked)
  2. Apply hard suitability rules per intervention type (no ponds on highways, etc.)
  3. Score cooling benefit vs cost -> cooling_per_rupee
  4. Greedily rank grid cells (highest cooling_per_rupee first)
  5. Export recommendation.csv (per-cell best option) and ranking.csv (priority-ordered list)

Swap USE_SYNTHETIC = False and set the two file paths once real data lands.
"""

"""
Member 3 - Decision Support
Urban Heat Island cooling-intervention recommender for Guwahati.

Pipeline:
  1. Load real grid data from Member 1 (Guwahati_Urban_Heat_Dataset.csv)
     - extract lat/lon centroids from the .geo column (don't wait on their fix)
     - derive a PROXY land-cover from NDVI/LST until Member 1 adds real WorldCover data
  2. Apply hard suitability rules per intervention type
  3. Score cooling benefit vs cost -> cooling_per_rupee
  4. Greedily rank grid cells (highest cooling_per_rupee first)
  5. Export recommendation.csv and ranking.csv

STATUS NOTE (2026-08-07): real dataset has no land_cover column yet (per Member 1/2
audit). This script uses a documented NDVI/LST-based PROXY so the pipeline runs
end-to-end today. Swap in real land_cover the moment Member 1 exports it (their
audit snippet D) - just change USE_PROXY_LANDCOVER to False, everything else
downstream is unchanged.
"""

import json
import numpy as np
import pandas as pd
from shapely.geometry import shape

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
USE_SYNTHETIC = False
DATASET_CSV = "/mnt/user-data/uploads/Guwahati_Urban_Heat_Dataset.csv"   # Member 1's real export
USE_PROXY_LANDCOVER = True   # flip to False once Member 1 adds real land_cover column
GRID_CELL_AREA_M2 = 100 * 100

BUDGET_RUPEES = 5_000_000

# ------------------------------------------------------------------
# STEP 0: LOAD DATA
# ------------------------------------------------------------------
def extract_centroid(geo_str):
    """Parse the .geo GeoJSON string GEE exports and return (lat, lon) centroid."""
    try:
        geom = shape(json.loads(geo_str))
        c = geom.centroid
        return pd.Series([c.y, c.x], index=["lat", "lon"])
    except Exception:
        return pd.Series([np.nan, np.nan], index=["lat", "lon"])


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

    df = pd.read_csv(DATASET_CSV)
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
# State clearly in your report/pitch that these are assumptions, not
# measured field data - that's honest and judges respect it.
# ------------------------------------------------------------------
INTERVENTIONS = {
    "trees": {
        "cost_per_cell": 5_000,
        "cooling_c": 0.8,
        # works on proxy categories now; add "hillslope" back once real land cover lands
        "allowed_land_cover": ["moderate", "bare_or_built_hot",
                                "vacant", "residential", "park", "hillslope"],
    },
    "pocket_park": {
        "cost_per_cell": 400_000,
        "cooling_c": 2.0,
        # deliberately NOT enabled on proxy data - proxy can't confirm a cell is
        # actually open/vacant land vs. a road or building. Real land_cover required.
        "allowed_land_cover": [] if USE_PROXY_LANDCOVER else ["vacant"],
        "min_cell_area_m2": GRID_CELL_AREA_M2,
    },
    "green_roof": {
        "cost_per_cell": 150_000,
        "cooling_c": 1.5,
        # same reasoning - needs confirmed building footprints, not proxy
        "allowed_land_cover": [] if USE_PROXY_LANDCOVER else ["building_dense"],
    },
    "cool_roof": {
        "cost_per_cell": 30_000,
        "cooling_c": 1.0,
        # safe on proxy: even if we can't tell building vs bare ground, a reflective
        # coating recommendation just becomes moot (not harmful) if it's not a roof -
        # unlike a pond, which would be actively wrong if placed on a road
        "allowed_land_cover": ["moderate", "bare_or_built_hot",
                                "building_dense", "residential"],
    },
}

NEVER_TOUCH = ["road", "highway", "water", "wetland"]

# ------------------------------------------------------------------
# STEP 2: RULE-BASED SUITABILITY FILTER
# ------------------------------------------------------------------
def suitable_interventions_for_cell(land_cover):
    """Return list of intervention names legally/physically valid for this cell."""
    if land_cover in NEVER_TOUCH:
        return []
    return [
        name for name, spec in INTERVENTIONS.items()
        if land_cover in spec["allowed_land_cover"]
    ]


def best_intervention_for_cell(row):
    """
    Among suitable options for a cell, pick the one with highest cooling_per_rupee.
    Returns (intervention_name, cost, cooling_c, cooling_per_rupee, exclusion_reason).
    """
    options = suitable_interventions_for_cell(row["land_cover"])
    if not options:
        reason = ("already vegetated - no action needed"
                   if row["land_cover"] == "vegetated"
                   else "excluded (never-touch land cover)")
        return pd.Series([None, None, None, None, reason],
                          index=["intervention", "cost_rupees", "cooling_c",
                                 "cooling_per_rupee", "exclusion_reason"])

    best = None
    for name in options:
        spec = INTERVENTIONS[name]
        cpr = spec["cooling_c"] / spec["cost_per_cell"]
        # Slightly favor cells that are already hotter and low-NDVI (more room to improve)
        heat_priority_boost = 1 + max(0, (row["predicted_temp"] - 35)) * 0.02
        adjusted_cpr = cpr * heat_priority_boost
        if best is None or adjusted_cpr > best[3]:
            best = (name, spec["cost_per_cell"], spec["cooling_c"], adjusted_cpr)

    return pd.Series(best + (None,), index=["intervention", "cost_rupees", "cooling_c",
                                             "cooling_per_rupee", "exclusion_reason"])


result = df.join(df.apply(best_intervention_for_cell, axis=1))

# Cells with no valid intervention (roads/water/etc.) are recorded, not silently dropped -
# transparency matters for the demo.
excluded = result[result["intervention"].isna()].copy()
recommendation = result[result["intervention"].notna()].copy()

print(f"Excluded: {len(excluded)} cells")
print(excluded["exclusion_reason"].value_counts())
print(f"Recommendable cells: {len(recommendation)}")

# ------------------------------------------------------------------
# STEP 3: GREEDY RANKING (cooling-per-rupee, budget-constrained)
# This is intentionally NOT an optimizer (no knapsack DP, no RL/GA).
# Sort descending by cooling_per_rupee, walk down, stop at budget.
# Simple, explainable, defensible in a 5-hour hackathon.
# ------------------------------------------------------------------
ranking = recommendation.sort_values("cooling_per_rupee", ascending=False).reset_index(drop=True)
ranking["rank"] = ranking.index + 1

if BUDGET_RUPEES is not None:
    ranking["cumulative_cost"] = ranking["cost_rupees"].cumsum()
    ranking["within_budget"] = ranking["cumulative_cost"] <= BUDGET_RUPEES
    n_selected = ranking["within_budget"].sum()
    print(f"Budget INR {BUDGET_RUPEES:,}: funds top {n_selected} of {len(ranking)} recommended cells")
else:
    ranking["within_budget"] = True

# ------------------------------------------------------------------
# STEP 4: EXPORT DELIVERABLES
# ------------------------------------------------------------------
recommendation_cols = ["grid_id", "lat", "lon", "land_cover", "predicted_temp",
                        "intervention", "cost_rupees", "cooling_c"]
recommendation.to_csv("recommendation.csv", index=False, columns=recommendation_cols)

excluded_cols = ["grid_id", "lat", "lon", "land_cover", "predicted_temp", "exclusion_reason"]
excluded.to_csv("excluded.csv", index=False, columns=excluded_cols)

ranking_cols = ["rank", "grid_id", "lat", "lon", "intervention", "cost_rupees",
                 "cooling_c", "cooling_per_rupee", "cumulative_cost", "within_budget"]
ranking.to_csv("ranking.csv", index=False, columns=[c for c in ranking_cols if c in ranking.columns])

print("\nSaved recommendation.csv and ranking.csv")
print("\nTop 5 priority interventions:")
print(ranking[["rank", "grid_id", "intervention", "cost_rupees", "cooling_c", "cooling_per_rupee"]].head())
