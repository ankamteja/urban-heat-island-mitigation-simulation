# Decision Support

Budget-constrained priority ranking of urban cooling interventions for
Guwahati's 100m grid, based on real land-cover classification and measured
land surface temperature.

```
Satellite data  →  Land cover + heat mapping  →  Decision Support  →  Interactive map
```

## Overview

Every 100m×100m grid cell in the study area is classified by land cover and
heat risk, then matched to a suitable cooling intervention where one
applies. This module determines three things in sequence:

1. **Where** an intervention is physically appropriate (suitability)
2. **What** intervention fits that location (action assignment)
3. **Which specific cells** should be funded first under a fixed budget
   (priority ranking)

## Features

| Feature | Description |
|---|---|
| Real suitability filter | Built on actual ESA WorldCover land-cover classification — water and wetland cells are hard-excluded; roof interventions are restricted to built-up land; ground interventions are restricted to open land |
| Cost-based scoring | Cost derived from real per-cell area and a per-square-metre unit rate |
| Cooling-per-rupee ranking | Every intervention type scored on °C reduced per rupee spent, so cool roofs, parks, and tree cover are compared on equal footing |
| Budget cutoff | Given a total budget, returns the exact set of cells that can be funded |
| Transparent exclusions | Every cell without a recommendation is recorded with an explicit reason, never silently dropped |
| Portable input path | Resolves the dataset relative to its own location in the repository — runs correctly on any machine that clones the project |

## Outputs

### `recommendation.csv`

Actionable cells, one row each.

| Column | Description |
|---|---|
| `grid_id` | Unique cell identifier |
| `lat`, `lon` | Cell centroid coordinates |
| `land_cover` | Classified land-cover type |
| `priority` | Heat tier (High / Medium) |
| `LST` | Measured land surface temperature (°C) |
| `NDVI` | Vegetation index |
| `recommended_action` | Cool roof / Green park / Tree cover |
| `cost_estimate` | Cost in INR, based on cell area and unit rate |
| `cooling_c` | Estimated temperature reduction (°C) |
| `cooling_per_rupee` | `cooling_c ÷ cost_estimate` — the ranking score |

**Recommended interventions by type:**

| Intervention | Cells | Rate (INR/m²) | Cooling (°C) |
|---|---:|---:|---:|
| Cool roof | 3,494 | 45.0 | 1.0 |
| Tree cover | 589 | 37.5 | 0.8 |
| Green park | 74 | 115.0 | 2.0 |

### `ranking.csv`

Actionable cells sorted by `cooling_per_rupee`, descending, with a running
cost total and a budget flag. At a demonstration budget of INR
10,00,00,000, this funds the top 299 cells, all Tree cover. Parks and cool roofs
fall below the cut once the park rate is anchored on real municipal figures.

### `excluded.csv`

3,987 cells excluded from recommendation, with reasons:

| Reason | Cells |
|---|---:|
| Already vegetated (tree cover) — no action needed | 3,752 |
| Never-touch land cover (water / wetland) | 193 |
| Low heat priority — no action needed | 42 |

## Land-cover classification

Real ESA WorldCover categories, mapped to suitability rules:

| Land cover | Cells | Rule |
|---|---:|---|
| Tree cover | 3,752 | Already vegetated — excluded, no action needed |
| Built-up | 3,523 | Roof-type interventions only (Cool roof) |
| Cropland | 573 | Ground-type interventions only |
| Water | 149 | Never touch |
| Grassland | 79 | Ground-type interventions only |
| Wetland | 44 | Never touch |
| Bare / sparse vegetation | 24 | Ground-type interventions only |

## Method

```
for each cell:
    if land_cover in [water, wetland]: exclude
    elif land_cover == tree_cover: exclude (already green)
    elif heat priority == Low: exclude
    elif land_cover == built_up: assign Cool roof
    elif land_cover in [bare_sparse, grassland, cropland]:
        assign Green park (if High priority) else Tree cover

for each actionable cell:
    cooling_per_rupee = cooling_c / cost_estimate

sort all cells by cooling_per_rupee, descending
accumulate cost while walking down the sorted list
mark cells within_budget = True until the budget is exhausted
```

A greedy ratio-ranking approach was used deliberately rather than an
optimizer. For a "maximize benefit per rupee under a fixed budget"
objective, this gives a reasonable, fully explainable result without the
added complexity of a solver, appropriate to the project's scope.

## Data source

Reads directly from the committed dataset at:
```
../Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv
```
resolved relative to this script's own location, so it runs unmodified on
any machine after cloning the repository — no absolute or user-specific
paths.

## Limitations

| Limitation | Cause | Path to resolution |
|---|---|---|
| Roads are not separately classified | ESA WorldCover has no dedicated road class — roads are folded into the built-up category alongside buildings | Ground-level interventions are restricted away from built-up cells entirely as a safeguard; full resolution would require a dedicated road layer (e.g. OpenStreetMap) |
| Cooling estimates (0.8 / 1.0 / 2.0°C) are engineering assumptions | Not measured or fitted to Guwahati-specific conditions | Future work: regression against tree canopy fraction and albedo |
| Cost varies only by intervention type, not individually by cell | Grid cells are near-uniform in area | Incorporate real per-cell cost variation (acquisition, access, condition) |

## Future improvements

- **Fitted cooling estimates.** Replace flat per-intervention assumptions
  with a regression against tree canopy fraction, albedo, and building
  density, once available.
- **Road-aware suitability.** Integrate a dedicated road layer (e.g.
  OpenStreetMap) to separate roads from buildings within the built-up
  class, enabling more precise placement.
- **Real per-cell cost variation.** Incorporate plot acquisition cost,
  rooftop condition, and access constraints so cost varies meaningfully
  between individual cells.
- **Phased, multi-year budgeting.** Produce a tranche-based rollout plan
  rather than a single budget cutoff, to support realistic funding cycles.
- **Equity-weighted ranking.** Optionally weight underserved areas above
  raw cooling-per-rupee, as an explicit, disclosed policy parameter layered
  on top of the existing ranking.
- **Interactive budget exploration.** A budget-input control that re-ranks
  and re-highlights the map in real time, without rerunning the pipeline
  manually.
