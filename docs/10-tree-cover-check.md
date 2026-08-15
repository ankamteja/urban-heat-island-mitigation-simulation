# 10 — Tree-cover temperature check

This page documents the one empirical cooling-related check that can be run
from the committed data alone. Its purpose is deliberately narrow: verify that
tree-cover cells are cooler than nearby built-up cells in the one Landsat scene
used by this project. It is not a validation of an intervention.

## Current result

The committed run pairs 1,391 ESA WorldCover tree-cover cells with distinct
nearby built-up cells (maximum separation 500 m; mean 126.5 m). Built-up cells
are **0.70 °C warmer on average** (descriptive bootstrap 95% interval: 0.65 to
0.75 °C); the median pair contrast is 0.50 °C.

The machine-readable values and the generated table are committed with the
pipeline results:

- [`tree_cover_cooling_validation.json`](../Machine%20Learning%20%26%20Prediction/Results/tree_cover_cooling_validation.json)
- [`tree_cover_cooling_validation.md`](../Machine%20Learning%20%26%20Prediction/Results/tree_cover_cooling_validation.md)

## Method

1. Read the canonical `dataset.csv` through `shared.uhi_shared.source_dataset_path()`.
2. Keep only ESA WorldCover code 10 (tree cover) and code 50 (built-up).
3. Convert the cell centroids to a local equirectangular metre grid.
4. For each tree-cover cell, find up to eight built-up candidates within 500 m.
5. Sort candidate pairs by distance and greedily retain one-to-one pairs. This
   prevents a single built-up cell being counted as the comparison for a large
   group of trees.
6. Report `built-up LST − tree-cover LST`. Positive numbers therefore mean the
   observed tree-cover cell is cooler.
7. Bootstrap the matched-pair mean 10,000 times with a fixed seed. The interval
   describes stability under resampling these pairs; it is not a causal
   confidence interval.

Run it after every dataset refresh:

```bash
python3 "Machine Learning & Prediction/scripts/validate_tree_cover_cooling.py"
```

The script overwrites the two result files above. Review and commit them with
the refreshed source dataset so the number is traceable to its exact inputs.

## What this supports

The result supports only this statement:

> In the committed Landsat scene, cells classified as tree cover are cooler
> than nearby matched cells classified as built-up.

It is reasonable evidence that the *direction* of a tree-cover cooling scenario
is not backwards. It also creates a reproducible baseline that can show whether
a future data refresh produces an implausible reversal.

## What this does not support

Do not call 0.70 °C the effect of planting a tree, and do not replace the
dashboard's 0.8 °C scenario value with it. The comparison is cross-sectional:
existing canopy is not the same treatment as a new planting. The groups can
differ in roof and paving materials, building density, shade geometry, terrain,
water proximity and land-cover classification error. All measurements also
come from one daytime Landsat overpass. The method offers no evidence about
cool roofs or green parks.

To estimate an intervention effect, the project would need repeated
before/after observations plus comparable untreated control locations, or a
properly designed field trial. Until then all `cooling_c` values remain planning
assumptions and the dashboard must be read as a scenario, not a forecast.
