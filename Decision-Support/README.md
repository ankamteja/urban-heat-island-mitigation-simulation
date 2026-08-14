# Decision Support

Budget-constrained priority ranking of urban cooling interventions for
Guwahati's 100m grid.

```
Satellite data  →  Heat risk tiering  →  Decision Support  →  Interactive map
```

## Overview

Every 100m×100m cell in the study area has a heat priority tier and a
suggested intervention (cool roof, green park, or tree cover). That
identifies *what* should happen where — it does not determine *order*.
A city cannot fund every recommended cell simultaneously. This module
produces the ranked, budget-constrained shortlist: given a fixed budget,
exactly which cells should be funded first.

The ranking is a deliberately simple greedy heuristic, not a solver: score
every cell by cooling delivered per rupee spent, sort descending, and walk
down the list until the budget is exhausted.

## Features

| Feature | Description |
|---|---|
| Suitability guardrail | Hard exclusion list for roads, highways, water bodies, and wetlands, implemented and ready to activate once a land-cover classification is available |
| Real cost scoring | Uses actual per-cell area × per-square-metre unit rate for cost, not a flat estimate |
| Cooling-per-rupee ranking | Every intervention type scored on °C reduced per rupee spent, so cool roofs, parks, and tree cover are compared on equal footing |
| Budget cutoff | Given a total budget, returns the exact set of cells that can be funded |
| Transparent exclusions | Every cell without a recommendation is recorded with an explicit reason, not silently dropped |

## Outputs

### `recommendation.csv`

All actionable cells, one row per cell.

| Column | Description |
|---|---|
| `grid_id` | Unique cell identifier |
| `lat`, `lon` | Cell centroid coordinates |
| `priority` | Heat tier (High / Medium) |
| `vegetation_class` | Vegetation category derived from NDVI |
| `LST` | Measured land surface temperature (°C) |
| `recommended_action` | Cool roof / Green park / Tree cover |
| `cost_estimate` | Cost in INR, based on cell area and unit rate |
| `cooling_c` | Estimated temperature reduction (°C) |
| `cooling_per_rupee` | `cooling_c ÷ cost_estimate` — the ranking score |

**Recommended interventions by type:**

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

## Method

```
for each actionable cell:
    cooling_per_rupee = cooling_c / cost_estimate

sort all cells by cooling_per_rupee, descending
accumulate cost while walking down the sorted list
mark cells within_budget = True until the budget is exhausted
```

A greedy ratio-ranking approach was chosen deliberately over an optimizer
(no knapsack solver, no genetic or reinforcement-learning approach). For a
"maximize benefit per rupee, subject to a budget" objective, greedy-by-ratio
gives a provably reasonable approximation, is fully explainable, and is
appropriate for the scope and timeline of this project.

## Limitations

| Limitation | Cause | Path to resolution |
|---|---|---|
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
