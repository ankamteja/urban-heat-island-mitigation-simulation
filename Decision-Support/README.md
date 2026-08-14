# Decision Support

Budget-constrained priority ranking of urban cooling interventions for
<<<<<<< HEAD
Guwahati's 100m grid.

```
Satellite data  →  Heat risk tiering  →  Decision Support  →  Interactive map
=======
Guwahati's 100m grid, based on real land-cover classification and measured
land surface temperature.

```
Satellite data  →  Land cover + heat mapping  →  Decision Support  →  Interactive map
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
```

## Overview

<<<<<<< HEAD
Every 100m×100m cell in the study area has a heat priority tier and a
suggested intervention (cool roof, green park, or tree cover). That
identifies *what* should happen where — it does not determine *order*.
A city cannot fund every recommended cell simultaneously. This module
produces the ranked, budget-constrained shortlist: given a fixed budget,
exactly which cells should be funded first.

The ranking is a deliberately simple greedy heuristic, not a solver: score
every cell by cooling delivered per rupee spent, sort descending, and walk
down the list until the budget is exhausted.
=======
Every 100m×100m grid cell in the study area is classified by land cover and
heat risk, then matched to a suitable cooling intervention where one
applies. This module determines three things in sequence:

1. **Where** an intervention is physically appropriate (suitability)
2. **What** intervention fits that location (action assignment)
3. **Which specific cells** should be funded first under a fixed budget
   (priority ranking)
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

## Features

| Feature | Description |
|---|---|
<<<<<<< HEAD
| Suitability guardrail | Hard exclusion list for roads, highways, water bodies, and wetlands, implemented and ready to activate once a land-cover classification is available |
| Real cost scoring | Uses actual per-cell area × per-square-metre unit rate for cost, not a flat estimate |
| Cooling-per-rupee ranking | Every intervention type scored on °C reduced per rupee spent, so cool roofs, parks, and tree cover are compared on equal footing |
| Budget cutoff | Given a total budget, returns the exact set of cells that can be funded |
| Transparent exclusions | Every cell without a recommendation is recorded with an explicit reason, not silently dropped |
=======
| Real suitability filter | Built on actual ESA WorldCover land-cover classification — water and wetland cells are hard-excluded; roof interventions are restricted to built-up land; ground interventions are restricted to open land |
| Cost-based scoring | Cost derived from real per-cell area and a per-square-metre unit rate |
| Cooling-per-rupee ranking | Every intervention type scored on °C reduced per rupee spent, so cool roofs, parks, and tree cover are compared on equal footing |
| Budget cutoff | Given a total budget, returns the exact set of cells that can be funded |
| Transparent exclusions | Every cell without a recommendation is recorded with an explicit reason, never silently dropped |
| Portable input path | Resolves the dataset relative to its own location in the repository — runs correctly on any machine that clones the project |
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

## Outputs

### `recommendation.csv`

<<<<<<< HEAD
All actionable cells, one row per cell.
=======
Actionable cells, one row each.
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

| Column | Description |
|---|---|
| `grid_id` | Unique cell identifier |
| `lat`, `lon` | Cell centroid coordinates |
<<<<<<< HEAD
| `priority` | Heat tier (High / Medium) |
| `vegetation_class` | Vegetation category derived from NDVI |
| `LST` | Measured land surface temperature (°C) |
=======
| `land_cover` | Classified land-cover type |
| `priority` | Heat tier (High / Medium) |
| `LST` | Measured land surface temperature (°C) |
| `NDVI` | Vegetation index |
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
| `recommended_action` | Cool roof / Green park / Tree cover |
| `cost_estimate` | Cost in INR, based on cell area and unit rate |
| `cooling_c` | Estimated temperature reduction (°C) |
| `cooling_per_rupee` | `cooling_c ÷ cost_estimate` — the ranking score |

**Recommended interventions by type:**

<<<<<<< HEAD
| Intervention | Cells | Total cost (INR) | Avg. cooling (°C) |
|---|---:|---:|---:|
| Green park | 4,072 | 90,76,49,819 | 2.0 |
| Tree cover | 1,955 | 65,36,37,330 | 0.8 |
| Cool roof | 81 | 4,33,39,471 | 1.0 |

### `ranking.csv`

Actionable cells sorted by `cooling_per_rupee`, with a running cost total
and a budget flag.

| rank | grid_id | recommended_action | cost_estimate | cooling_per_rupee | within_budget |
|---:|---|---|---:|---:|---|
| 1 | +102200+29171 | Green park | 2,22,803 | 8.98×10⁻⁶ | True |
| 2 | +102198+29171 | Green park | 2,22,803 | 8.98×10⁻⁶ | True |
| 3 | +102199+29171 | Green park | 2,22,803 | 8.98×10⁻⁶ | True |

At a demonstration budget of INR 10,00,00,000, this ranking funds the top
448 of 6,108 actionable cells.

### `excluded.csv`

Cells without a recommendation, with a stated reason. Currently 2,036
cells, all tagged "Low priority — no action needed." The road/water
exclusion path exists in the logic but has not yet excluded any cells,
since a land-cover classification distinguishing roads and water bodies is
not yet available (see Limitations).
=======
| Intervention | Cells | Rate (INR/m²) | Cooling (°C) |
|---|---:|---:|---:|
| Cool roof | 3,494 | 60.0 | 1.0 |
| Tree cover | 589 | 37.5 | 0.8 |
| Green park | 74 | 25.0 | 2.0 |

### `ranking.csv`

Actionable cells sorted by `cooling_per_rupee`, descending, with a running
cost total and a budget flag. At a demonstration budget of INR
10,00,00,000, this funds the top 323 cells (74 Green park, 249 Tree cover).

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
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

## Method

```
<<<<<<< HEAD
=======
for each cell:
    if land_cover in [water, wetland]: exclude
    elif land_cover == tree_cover: exclude (already green)
    elif heat priority == Low: exclude
    elif land_cover == built_up: assign Cool roof
    elif land_cover in [bare_sparse, grassland, cropland]:
        assign Green park (if High priority) else Tree cover

>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
for each actionable cell:
    cooling_per_rupee = cooling_c / cost_estimate

sort all cells by cooling_per_rupee, descending
accumulate cost while walking down the sorted list
mark cells within_budget = True until the budget is exhausted
```

<<<<<<< HEAD
A greedy ratio-ranking approach was chosen deliberately over an optimizer
(no knapsack solver, no genetic or reinforcement-learning approach). For a
"maximize benefit per rupee, subject to a budget" objective, greedy-by-ratio
gives a provably reasonable approximation, is fully explainable, and is
appropriate for the scope and timeline of this project.
=======
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
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb

## Limitations

| Limitation | Cause | Path to resolution |
|---|---|---|
<<<<<<< HEAD
| Road, water, and building exclusion not yet active | Land-cover classification not yet available from the satellite processing pipeline | Requires a completed land-cover export |
| Cooling estimates (0.8 / 1.0 / 2.0°C) are engineering assumptions | Not measured or fitted to Guwahati-specific conditions | Future work: regression against tree canopy fraction and albedo |
| Ranking output forms three cost blocks rather than a smooth priority order | Grid cells are near-uniform in area, so cost varies minimally within an intervention type | Resolved once real per-cell cost variation (acquisition, access, condition) is incorporated |
| Underlying NDVI values are compressed relative to expected range | A rescaling step was omitted in the upstream satellite processing script | Fix identified; pending a corrected data export |

## Future improvements

- **Fitted cooling estimates.** Replace the flat per-intervention cooling
  assumptions with a regression against tree canopy fraction, albedo, and
  building density once available, so rankings reflect measured local
  effects rather than general engineering estimates.
- **Real per-cell cost variation.** Incorporate plot acquisition cost,
  rooftop condition, and access constraints so cost differs meaningfully
  between individual cells rather than only between intervention types.
- **Phased, multi-year budgeting.** Produce a tranche-based rollout plan
  (e.g. Year 1 / Year 2 / Year 3) rather than a single budget cutoff, to
  support realistic municipal planning cycles.
- **Equity-weighted ranking.** Optionally weight underserved areas above
  raw cooling-per-rupee, as an explicit, disclosed policy parameter layered
  on top of the existing ranking rather than embedded silently within it.
- **Interactive budget exploration.** A budget-input control that
  re-ranks and re-highlights the map in real time, allowing exploration of
  outcomes at different funding levels without rerunning the pipeline.
- **Suitability filter activation.** The highest-priority next step:
  once a land-cover classification is available, activating the existing
  exclusion logic will ensure recommendations respect real-world
  constraints such as roads and water bodies.
=======
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
>>>>>>> 42cdcdaa5d037a606c1f3926dfa7bfc538e252eb
