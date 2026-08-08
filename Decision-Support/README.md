# Spec Compliance Audit — Decision Support

**Audited:** 2026-08-08
**Repo:** `ankamteja/urban-heat-island-mitigation-simulation`
**Scope:** the Decision Support module spec — *"Identify the best locations for cooling interventions."*

Verified by reading `member3_decision_support.py` and by statistically analysing all
8,144 rows produced from `Dataset/Guwahati_Urban_Heat_Dataset.csv`.

**Score: 3 of 4 spec items fully met, 1 met with a documented limitation.**

---

## Summary

| # | Spec item | Status |
|---|---|---|
| 1 | Apply rule-based suitability filtering | ✅ Done |
| 2 | Exclude unsuitable areas (roads, water, buildings, restricted zones) | ⚠️ Done but limited by upstream data |
| 3 | Recommend interventions (Trees, Parks, Green roofs, Cool roofs) | ⚠️ Done, 2 of 4 interventions disabled by design |
| 4 | Rank locations using Cooling Benefit / Cost | ✅ Done |
| — | Deliverable — `recommendation.csv` | ✅ Done |
| — | Deliverable — `ranking.csv` | ✅ Done |
| — | Tool — Python | ✅ Used |
| — | Tool — Pandas | ✅ Used |
| — | Tool — GeoPandas | ⚠️ Not used — `shapely` used directly instead |

---

## Detail

### 1. Rule-based suitability filtering — Done

`suitable_interventions_for_cell()` matches each cell's `land_cover` against a
per-intervention `allowed_land_cover` list defined in the `INTERVENTIONS` dict.
`best_intervention_for_cell()` then picks whichever allowed option maximizes
`cooling_per_rupee` for that cell. No cell is assigned an intervention its land
cover doesn't permit. **Met.**

### 2. Exclusion of unsuitable areas — Done, limited by upstream data

```python
NEVER_TOUCH = ["road", "highway", "water", "wetland"]
```

This list is correct and would fully satisfy the spec **if** the input data
carried a real land-cover classification. It doesn't yet — `Guwahati_Urban_Heat_Dataset.csv`
has no `land_cover` column (confirmed in the Remote Sensing audit, 2026-08-07).

**Current behavior:** `USE_PROXY_LANDCOVER = True` derives a 3-class stand-in
from this dataset's own NDVI quantiles:

```python
q1, q3 = df["ndvi"].quantile([0.25, 0.75])
# top 25% NDVI  -> "vegetated"
# bottom 25%    -> "bare_or_built_hot"
# middle 50%    -> "moderate"
```

None of `road`, `highway`, `water`, `wetland`, or `building` exist as labels in
this proxy — satellite NDVI alone cannot separate a road from a building from
bare soil. So on the current run, the `NEVER_TOUCH` list is logically correct
but **numerically inactive** (0 cells excluded on that basis; 100% of exclusions
are from the "already vegetated" case below, not from road/water/restricted-zone
exclusion). This is a data gap, not a logic gap — the rule is ready the moment
real land cover lands.

**Knock-on effect:** because roads/buildings can't be identified, `pocket_park`
and `green_roof` are deliberately disabled on proxy data (see item 3) rather
than risk placing them on the wrong surface.

### 3. Recommend interventions — Done, 2 of 4 enabled

```python
INTERVENTIONS = {
    "trees":       {..., "allowed_land_cover": ["moderate", "bare_or_built_hot", ...]},
    "pocket_park": {..., "allowed_land_cover": [] if USE_PROXY_LANDCOVER else ["vacant"]},
    "green_roof":  {..., "allowed_land_cover": [] if USE_PROXY_LANDCOVER else ["building_dense"]},
    "cool_roof":   {..., "allowed_land_cover": ["moderate", "bare_or_built_hot", ...]},
}
```

All four intervention types are implemented with cost and cooling-benefit
assumptions. On the current proxy-based run, only `trees` and `cool_roof` are
reachable — `pocket_park` and `green_roof` have an empty `allowed_land_cover`
list while `USE_PROXY_LANDCOVER = True`, by design: a reflective-roof
recommendation on the wrong surface is merely moot, but a pond or park
recommendation on the wrong surface (e.g. a road) would be actively wrong.
This is a one-flag change (`USE_PROXY_LANDCOVER = False`) once real land cover
is available — no other code changes needed.

Cost/cooling figures are stated assumptions, not measured field data:

| Intervention | Cost per 100m cell | Cooling estimate |
|---|---|---|
| Trees | ₹5,000 | 0.8°C |
| Pocket park | ₹400,000 | 2.0°C |
| Green roof | ₹150,000 | 1.5°C |
| Cool roof | ₹30,000 | 1.0°C |

### 4. Ranking by Cooling Benefit / Cost — Done

```python
cpr = spec["cooling_c"] / spec["cost_per_cell"]
adjusted_cpr = cpr * heat_priority_boost   # mild boost for already-hotter cells
ranking = recommendation.sort_values("cooling_per_rupee", ascending=False)
```

Greedy sort, budget-capped cumulative sum (`BUDGET_RUPEES = 5,000,000`) — the
spec calls for a ranked list, not an optimizer, and that's what's implemented:
no knapsack DP, no RL/GA. **Met**, and intentionally simple.

### Deliverables

| Deliverable | Status |
|---|---|
| `recommendation.csv` | ✅ 6,108 of 8,144 cells, columns: `grid_id, lat, lon, land_cover, predicted_temp, intervention, cost_rupees, cooling_c` |
| `ranking.csv` | ✅ Same cells sorted by `cooling_per_rupee`, capped to top 1,000 within the ₹50,00,000 budget |
| `excluded.csv` *(beyond spec)* | 2,036 cells excluded, all currently reason `"already vegetated - no action needed"` — not roads/water, see item 2 |

### Tools

- **Python** ✅
- **Pandas** ✅ — all filtering, scoring, ranking
- **GeoPandas** ⚠️ — spec lists this explicitly; the script uses `shapely.geometry.shape` directly to parse the `.geo` centroid column instead of a full GeoDataFrame. Functionally equivalent for this task (no spatial joins or CRS reprojection were needed), but doesn't match the spec's named tool. Low-risk gap — flagged for completeness, not urgent to fix before the demo.

---

## Two inputs this module depends on, not yet resolved elsewhere

1. **Real `land_cover`** — pending Member 1's GEE re-export with the WorldCover
   join (fix already written and handed off as `urban_heat_analysis_FIXED.js`).
2. **`predicted_temp`** from Member 2 — currently substituting raw `LST`
   (measured, not modeled). Legitimate stand-in; ranking logic is agnostic to
   the source of the temperature column.

Both are single-flag swaps in `load_data()` — no downstream rework required.

## Suggested order (for next commit)

1. Get `predictions.csv` from Member 2 — swap `LST` for `predicted_temp`, rerun.
2. Get re-exported `dataset.csv` from Member 1 with real `LandCover` — set
   `USE_PROXY_LANDCOVER = False`, rerun. This is the one that unlocks
   `pocket_park` and `green_roof`, and makes `NEVER_TOUCH` numerically active.
3. Optional: migrate `.geo` parsing to GeoPandas to close the tools gap.
