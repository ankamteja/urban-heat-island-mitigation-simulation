# Machine Learning & Prediction - Guwahati

## Module Overview

This module consumes the grid dataset produced by the
[Remote Sensing & Data Engineering](../Remote%20Sensing%20%26%20Data%20Engineering/)
module and turns it into dashboard-ready mitigation guidance.

Pipeline:

```
Guwahati_Urban_Heat_Dataset.csv
        |
        v
1. preprocess.py           parse geometry, derive Latitude/Longitude
        |
        v
2. train_regression.py     LST regression, metrics, saved model
        |
        v
3. tier_and_recommend.py   priority tiers, actions, cost estimates
        |
        v
4. export_grid_geojson.py  grid.geojson for the frontend dashboard
```

---

## READ THIS FIRST - the NDVI caveat

**Every NDVI and Heat_Risk figure in this module is biased, and the bias cannot be
repaired here.**

The source `NDVI` column was computed in Google Earth Engine from **raw DN values**
without the Landsat Collection 2 Level 2 surface-reflectance rescale
(`x 0.0000275 - 0.2`). This is documented as item #3 / "Fix A" in the
[Remote Sensing SPEC_AUDIT](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md).

**We do not correct it, because the correction is mathematically non-invertible from
the exported CSV.** `NDVI_wrong` depends only on the *ratio* of the two band DNs;
`NDVI_correct` also depends on their *sum*, and the sum was never exported. Three
different band pairs that all yield the same wrong NDVI:

| Raw NIR | Raw RED | NDVI as exported | NDVI if correctly rescaled |
|---|---|---|---|
| 20000 | 10000 | 0.3333 | **0.6471** |
| 40000 | 20000 | 0.3333 | **0.4400** |
| 12000 | 6000 | 0.3333 | **1.7368** (physically degenerate) |

One exported value, many possible true values. Recovering real NDVI requires
re-running the GEE script with Fix A applied and re-exporting.

Consequences, which apply to every output in `Results/`:

- All NDVI values are compressed toward zero (observed max **0.386**; healthy
  vegetation should reach 0.7-0.85).
- `Heat_Risk` subtracts NDVI, so it is **biased high** - vegetation is
  systematically under-credited as a cooling factor.
- Priority tiers and recommended actions derive from `Heat_Risk`, so they inherit
  the bias. Treat them as indicative ranks, not calibrated risk levels.

**For future contributors:** this module applies **no** NDVI correction of its own.
Fixing item A upstream in the GEE script and re-exporting is therefore safe - there
is no double-correction hazard. The pipeline reads whatever `NDVI` column it is
given, so a corrected export needs **zero code changes here**; only the
`VEGETATION_SPLIT_QUANTILE` constant in `tier_and_recommend.py` should be revisited
(see section 4).

Full detail: [SPEC_AUDIT.md](./SPEC_AUDIT.md).

---

# 1. Preprocessing

`scripts/preprocess.py` - input `../Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv`,
output `Results/preprocessed.csv`.

Steps:

- Parse the `.geo` column (per-row GeoJSON polygon strings) into shapely geometries.
- Derive scalar `Longitude` / `Latitude` from each cell's polygon centroid. **This
  closes gaps #7 and #8 of the Remote Sensing SPEC_AUDIT without waiting on a GEE
  re-run** - the coordinates were always present, just trapped inside the `.geo`
  polygon.
- Drop `system:index` (duplicate of `grid_id`) and `count` (constant `1` across all
  8,144 rows - confirms one 100 m pixel per cell, but carries no analytical signal).
- Retain the original `.geo` string as `geo_json` so step 4 reproduces the source
  polygons byte-for-byte with no reprojection.

Verified output:

| Property | Value |
|---|---|
| Rows | 8,144 (no nulls) |
| Longitude range | 91.65286 to 91.83163 |
| Latitude range | 26.10190 to 26.20790 |

---

# 2. Heat_Risk is not an independent variable

Preprocessing asserts an identity that determines the whole modelling approach:

```
Heat_Risk == unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)
          == (LST - 20) / 14 - (NDVI + 0.2)
```

Measured maximum residual across all 8,144 rows: **1.41e-15** - floating-point
noise. `Heat_Risk` is a **closed-form function** of `LST` and `NDVI`, not a separate
measurement.

---

# 3. Regression Model

`scripts/train_regression.py` - output `Models/heat_risk_model.pkl`,
`Results/metrics.md`, `Results/metrics.json`, plus two plots.

## Target: LST, not Heat_Risk

Because of the identity in section 2, regressing `Heat_Risk` on a feature set that
includes `NDVI` would be **algebraic identity recovery, not learning** - the model
would simply rediscover the `-1` coefficient on the NDVI term. So the target is
**`LST`** (degrees C):

- it is the physically measured quantity,
- it is measured independently of NDVI,
- it is exactly what the dashboard renders as `temperature`,
- and `Heat_Risk` remains recoverable from a predicted LST via the identity above.

## Features

| Feature | Notes |
|---|---|
| `NDVI` | Uncorrected - see the caveat above |
| `Latitude` | Derived centroid |
| `Longitude` | Derived centroid |
| `LST_lag_k8` | *Optional set only.* Mean LST of the 8 nearest **training** cells |

The spatial-lag feature is fitted on training-set neighbours only. Including test
cells among the neighbours would leak each test cell's own target into its feature.

## Two splits, because one of them is misleading

A random 80/20 split on a 100 m grid is **optimistic**: adjacent cells are near
duplicates, so nearly every held-out cell has a near-twin in training. The model can
score well by spatial interpolation without learning anything transferable. So a
**spatially blocked** split (6x6 = 36 contiguous blocks, whole blocks held out) is
reported alongside it, as an honest "unseen neighbourhood" estimate.

## Results

Seed `42`, 8,144 rows, 20% held out.

| Split | Features | Model | RMSE (C) | MAE (C) | R2 |
|---|---|---|---|---|---|
| random_80_20 | base | LinearRegression | 1.4363 | 1.0917 | 0.2475 |
| random_80_20 | base | RandomForest | 0.5209 | 0.3844 | **0.9010** |
| random_80_20 | base+spatial_lag | LinearRegression | 0.4262 | 0.3194 | 0.9337 |
| random_80_20 | base+spatial_lag | RandomForest | 0.4125 | 0.3088 | 0.9379 |
| spatial_block | base | LinearRegression | 1.4810 | 1.3196 | -0.6136 |
| spatial_block | base | RandomForest | 1.0742 | 0.7399 | **0.1510** |
| spatial_block | base+spatial_lag | LinearRegression | 1.2017 | 0.8990 | -0.0624 |
| spatial_block | base+spatial_lag | RandomForest | 1.1801 | 0.8892 | -0.0245 |

### Interpretation - do not quote the 0.90

**The headline number for this model is R2 = 0.15, not 0.90.**

RandomForest scores R2 **0.9010** on the random split but **0.1510** on the spatial
block split - the same model, same features. That collapse is the finding: the 0.90
is almost entirely **spatial memorisation of latitude/longitude**, not a learned
vegetation-to-temperature relationship. The model interpolates between neighbouring
cells it has already seen; move it to an unseen part of the city and it barely beats
predicting the mean.

Both LinearRegression variants go **negative** under blocking (worse than predicting
the mean), confirming there is no usable global linear structure.

Honest conclusions:

- **Valid use:** interpolating LST for gaps *inside* the already-surveyed extent.
- **Not valid:** predicting temperature for new areas, other cities, or future dates.
- The weak NDVI signal (correlation with LST is only **-0.279**) is itself partly an
  artifact of the NDVI bias - a correct NDVI would likely carry more signal. This
  cannot be confirmed without the GEE re-run.

RandomForest is the right ceiling for this problem regardless: 8,144 rows and 3-4
features do not justify anything heavier, and nothing deeper would fix a data
limitation.

## Saved model

`Models/heat_risk_model.pkl` holds the **base-feature RandomForest on the random
split**, chosen because the base set is the only configuration valid for the actual
use case - estimating temperature from vegetation and location. The spatial-lag
variant needs neighbouring cells' *measured* LST, so it can only gap-fill inside a
surveyed area.

The filename is `heat_risk_model.pkl` for continuity with the module spec, but **the
target is LST**. The artifact is a dict carrying `target`, `features`,
`random_state`, `config`, and `ndvi_corrected: False` alongside the estimator, so a
consumer cannot mistake what it predicts.

---

# 4. Priority Tiering

`scripts/tier_and_recommend.py` - output `Results/tiered.csv`,
`Results/tiering_summary.md`, `Results/priority_map.png`.

**There is no labelled ground truth for "priority" or "recommended action" anywhere
in this project.** This step is therefore an explicit rule engine, not a supervised
classifier pretending to have learned them. Every threshold is a named constant in
the script.

## Priority - quantile bins on Heat_Risk

Quantiles rather than absolute cutoffs, because `Heat_Risk` sits on a biased scale
and an absolute threshold would be calibrated to that bias.

| Tier | Rule | Cutoff (computed) | Cells |
|---|---|---|---|
| Low | `Heat_Risk <= q0.25` | <= 0.005661 | 2,036 |
| Medium | between | 0.005661 to 0.241290 | 4,072 |
| High | `Heat_Risk >= q0.75` | >= 0.241290 | 2,036 |

A uniform bias would cancel out of a *ranking*. This one does not: the NDVI error is
brightness-dependent, so it compresses the NDVI term's variance unevenly and leaves
`Heat_Risk` over-weighted toward LST. Tier boundaries are approximate even as ranks.

## Vegetation split

The action table needs a "vegetated vs sparse" split. The literature threshold is
NDVI ~0.3 - but the uncorrected NDVI has a **p95 of only 0.295**, so an absolute 0.3
would label essentially the whole city sparse and collapse the table. We split at the
dataset **median, NDVI = 0.179546**, a within-city relative measure.

**When Fix A lands upstream, change `VEGETATION_SPLIT_QUANTILE` to an absolute 0.3
threshold.**

## Decision table

Keyed on `(priority, vegetation_class)`. The four action names are fixed by the
dashboard - `frontend/js/popup.js` renders them verbatim.

| Priority | Vegetation | Action | Rationale |
|---|---|---|---|
| High | sparse | `Tree cover` | Hot with little vegetation - plant |
| High | vegetated | `Cool roof` | Hot but already green - treat surfaces instead |
| Medium | sparse | `Green park` | Moderate - amenity-scale intervention |
| Medium | vegetated | `Green park` | Moderate - amenity-scale intervention |
| Low | sparse | `None` | Not a priority |
| Low | vegetated | `None` | Not a priority |

Note the `High / vegetated` cell is rare by construction - only **81 cells**. High
`Heat_Risk` requires low NDVI almost by definition, since `Heat_Risk` subtracts NDVI.

---

# 5. Cost Estimates

**The unit rates below are planning placeholders, not fitted, tendered, or surveyed
costs.** They are order-of-magnitude figures chosen so the dashboard can rank cells
by relative investment. Replace them with real municipal unit rates before any figure
here informs a budget.

```
cost_estimate = cell_area_m2 x inr_per_m2 x coverage_fraction
```

| Action | INR / m2 | Coverage fraction | Reasoning for coverage |
|---|---|---|---|
| `Tree cover` | 150 | 0.25 | Planting a quarter of a cell is realistic |
| `Cool roof` | 400 | 0.15 | Only roof area, not the whole cell |
| `Green park` | 250 | 0.10 | One pocket park per cell |
| `None` | 0 | 0.00 | No intervention |

`coverage_fraction` exists because treating 100% of a cell is not physically possible
- cells contain roads, buildings and water.

Cell area is computed from each polygon's own bounds via a local equirectangular
conversion (`M_PER_DEG_LAT = 110574`, `M_PER_DEG_LON_EQUATOR = 111320`), exact for
these axis-aligned rectangles. Measured mean: **8,916 m2** - an independent
confirmation of the 89.8 m x 99.3 m cell geometry reported in Remote Sensing
SPEC_AUDIT item #6.

Resulting programme totals:

| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) |
|---|---|---|---|---|---|
| High | Cool roof | 81 | 29.47 | 0.210 | 43,339,471 |
| High | Tree cover | 1,955 | 28.70 | 0.115 | 653,637,330 |
| Medium | Green park | 4,072 | 27.17 | 0.181 | 907,649,819 |
| Low | None | 2,036 | 24.92 | 0.243 | 0 |

**Total notional programme cost: INR 1,604,626,620** (~INR 160 crore, placeholder
rates).

---

# 6. Dataset Features Produced

`Results/tiered.csv` columns:

| Feature | Source | Description |
|---|---|---|
| `grid_id` | passthrough | Unique grid identifier |
| `LST` | passthrough | Land surface temperature, degrees C |
| `NDVI` | passthrough | Vegetation index - **uncorrected** |
| `Heat_Risk` | passthrough | Normalised LST minus normalised NDVI - **biased high** |
| `Latitude` | **derived** | Cell centroid latitude (closes SPEC_AUDIT #7) |
| `Longitude` | **derived** | Cell centroid longitude (closes SPEC_AUDIT #8) |
| `vegetation_class` | **derived** | `sparse` / `vegetated`, split at NDVI median |
| `priority` | **derived** | `High` / `Medium` / `Low` |
| `recommended_action` | **derived** | One of four dashboard actions |
| `cell_area_m2` | **derived** | Metric cell area, ~8,916 m2 |
| `cost_estimate` | **derived** | INR, placeholder rates |
| `geo_json` | passthrough | Original `.geo` polygon string |

---

# 7. Frontend Integration

`scripts/export_grid_geojson.py` writes `Results/grid.geojson` - 8,144 features,
3.52 MB.

Feature properties are **exactly** the six keys the existing dashboard reads, verified
identical to `frontend/mock_data/grid.geojson`:

```
grid_id, temperature, ndvi, priority, recommended_action, cost_estimate
```

Renames applied: `LST` -> `temperature`, `NDVI` -> `ndvi`. `cost_estimate` is an
`int` because `popup.js` calls `.toLocaleString()` on it. The export script validates
the key set on every feature and fails loudly rather than shipping a file the
dashboard cannot render.

## This module does not switch the dashboard over

`frontend/mock_data/grid.geojson` is left untouched on purpose, so that moving from
mock to real data is a visible, reviewable one-line diff rather than a silent data
swap. To make the switch, change `frontend/js/main.js:1`:

```diff
-loadGrid('mock_data/grid.geojson')
+loadGrid('../Machine Learning & Prediction/Results/grid.geojson')
```

(or copy `Results/grid.geojson` into `frontend/mock_data/` if you prefer to keep the
frontend self-contained for static hosting).

## Two frontend follow-ups this export exposes

1. **The temperature legend needs retuning.** `mapView.js` `TEMP_COLOR_SCALE` buckets
   at 30 / 34 / 38 C, but real LST spans only **20.9 to 33.1 C**. Measured distribution
   of the 8,144 real cells across the current bands:

   | Legend band | Share of cells |
   |---|---|
   | `< 30 C` | **98.6%** |
   | `30-34 C` | 1.4% |
   | `34-38 C` | 0.0% - never used |
   | `> 38 C` | 0.0% - never used |

   Half the legend is dead and the choropleth is effectively one flat colour. The mock
   data ran 28-42 C, which is why this never showed up. Suggested real-data buckets:
   **25 / 27.5 / 30 / above**. The heat layer itself is unaffected - `renderHeatLayer`
   min-max normalises its own intensities.
2. **8,144 cells vs the mock's 900.** Worth checking pan/zoom performance; the
   invisible `renderGridLayer` polygons exist only for popup hit-testing, so
   canvas rendering (`L.geoJSON(..., { renderer: L.canvas() })`) is the fix if it
   drags.

---

# 8. Tools Used

## Python

| Package | Version | Used for |
|---|---|---|
| pandas | 3.0.5 | Tabular pipeline |
| numpy | 2.4.6 | Numerics, seeded RNG |
| scikit-learn | 1.9.0 | RandomForest, LinearRegression, NearestNeighbors, metrics |
| shapely | 2.1.2 | GeoJSON polygon parsing, centroids, bounds |
| matplotlib | 3.11.0 | Plots (Agg backend, headless) |
| joblib | 1.5.3 | Model serialisation |
| scipy | 1.18.0 | scikit-learn dependency |

**geopandas / fiona / pyproj are deliberately not required.** The `.geo` column is
plain GeoJSON, so `shapely` + `json` cover all geometry work without pulling in the
GDAL stack. This also closes the "Python not used" gap in the Remote Sensing
SPEC_AUDIT tools table.

## Reproducibility

All seeds fixed (`RANDOM_STATE = 42`); dependency versions pinned in
`requirements.txt`. Re-running the pipeline reproduces every number in this README.

---

# How to Run

```bash
pip install -r requirements.txt

python scripts/preprocess.py
python scripts/train_regression.py
python scripts/tier_and_recommend.py
python scripts/export_grid_geojson.py
```

Each script is independently runnable and resolves paths relative to its own
location, so the working directory does not matter. They must run in the order above -
each consumes the previous one's output.

---

# Module Structure

```
Machine Learning & Prediction
|
├── README.md
├── SPEC_AUDIT.md
├── requirements.txt
|
├── scripts
│   ├── preprocess.py
│   ├── train_regression.py
│   ├── tier_and_recommend.py
│   └── export_grid_geojson.py
|
├── Models
│   └── heat_risk_model.pkl
|
└── Results
    ├── preprocessed.csv
    ├── tiered.csv
    ├── grid.geojson
    ├── metrics.md
    ├── metrics.json
    ├── tiering_summary.md
    ├── pred_vs_actual.png
    ├── feature_importances.png
    └── priority_map.png
```

---

# Future Improvements

Ordered by how much they would change the conclusions:

1. **Re-run GEE with SPEC_AUDIT Fix A and re-export.** Everything about the NDVI
   relationship in this module is provisional until this lands. No code changes needed
   here.
2. **Join land cover** (SPEC_AUDIT items #11/#12, ESA WorldCover). A land-cover class
   per cell would give the model a genuinely independent predictor - the single most
   likely fix for the R2 = 0.15 generalisation failure, since built-up fraction drives
   surface temperature far more than the current feature set can express.
3. **Add NDBI** (SPEC_AUDIT #4) as a built-up proxy - cheaper than land cover, same
   direction.
4. **Multi-temporal LST** (seasonal or diurnal composites) to model heat over time
   rather than a single annual median.
5. **Validate the cost heuristics** against actual municipal unit rates.
6. **Ground-truth the priority tiers** against a planner's assessment, which would
   make a supervised classifier legitimate here for the first time.
