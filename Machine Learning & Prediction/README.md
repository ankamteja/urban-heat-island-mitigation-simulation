# Machine Learning & Prediction - Guwahati

## Module Overview

Consumes the grid dataset produced by the
[Remote Sensing & Data Engineering](../Remote%20Sensing%20%26%20Data%20Engineering/)
module and turns it into the dashboard-ready mitigation guidance the frontend
renders.

```
Remote Sensing & Data Engineering/Dataset/dataset.csv
        |
        v
1. preprocess.py           parse geometry, derive centroids, carry land cover
        |
        v
2. train_regression.py     LST regression, metrics, saved model
        |
        v
3. tier_and_recommend.py   priority tiers, land-cover-gated actions, costs
        |
        v
4. export_grid_geojson.py  grid.geojson -> Results/ and frontend/data/
```

Every number in this README is reproduced by running the pipeline. Seeds are
fixed and CI re-runs it on every push, failing if the committed outputs drift.

---

# 1. Preprocessing

`scripts/preprocess.py` - reads `dataset.csv`, writes `Results/preprocessed.csv`.

- Resolves the source dataset through `shared.source_dataset_path()` rather than
  a hardcoded filename. The file was renamed once (`Guwahati_Urban_Heat_Dataset.csv`
  -> `dataset.csv`) and both consuming modules kept the old name, so both crashed
  on a clean clone. One definition now, in `shared/constants.json`.
- Refuses to run if `LandCover`, `NDBI` or `Vegetation` are absent. Their absence
  means you are reading the superseded pre-fix export.
- Parses `.geo` polygons and derives each cell's centroid.
- Attaches a readable `land_cover` label to the numeric WorldCover code.
- **Carries `LandCover`, `NDBI` and `Vegetation` forward.** This step used to
  select seven columns and drop them, which is what left the rule engine blind to
  land cover - see section 4.
- Verifies the Heat_Risk identity (section 2).

Verified output:

| Property | Value |
|---|---|
| Rows | 8,144 (no nulls) |
| NDVI range | -0.416 to 0.781 |
| Longitude range | 91.65286 to 91.83163 |
| Latitude range | 26.10190 to 26.20790 |

## The NDVI provenance check

An earlier Earth Engine script computed NDVI from raw DN values without the
Landsat Collection 2 Level 2 surface-reflectance rescale (`x 0.0000275 - 0.2`),
which compressed the whole city below 0.39 and biased `Heat_Risk` high.

**That has been fixed upstream.** The committed dataset reaches NDVI 0.781.

The correction was never recoverable here, and that is worth recording: NDVI
computed from raw DN depends only on the *ratio* of the two bands, while the
correct value also depends on their *sum*, which was never exported. Three band
pairs yielding the same wrong 0.3333 give true values of 0.6471, 0.4400 and a
physically degenerate 1.7368. Only a re-export could fix it, and it did.

The scripts no longer hardcode a caveat about this. They **derive** it -
`shared.ndvi_looks_corrected()` checks whether the observed range is consistent
with surface reflectance, and warns only if it is not. A hardcoded caveat about
data is wrong the moment the data changes, which is exactly what happened: every
script in this repository kept printing "NDVI is UNCORRECTED" for weeks after
the corrected export had been committed, directly above a line showing the
corrected range.

---

# 2. Heat_Risk is not an independent variable

```
Heat_Risk == unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)
```

Maximum residual across all 8,144 rows: **1.52e-15** - floating-point noise.
`Heat_Risk` is a closed-form function of `LST` and `NDVI`, not a separate
measurement. This determines the modelling target in section 3, and
`preprocess.py` re-asserts it on every run so a formula drift upstream fails
loudly.

---

# 3. Regression Model

`scripts/train_regression.py` - writes `Models/heat_risk_model.pkl`,
`Results/metrics.md`, `Results/metrics.json`, and two plots.

## Target: LST, not Heat_Risk

Because of the identity above, regressing `Heat_Risk` on a feature set
containing `NDVI` would be algebraic identity recovery, not learning. The target
is **`LST`** (degrees C): the physically measured quantity, measured
independently of NDVI, and exactly what the dashboard renders as `temperature`.

## Features

| Feature | Correlation with LST | Notes |
|---|---|---|
| `NDBI` | **+0.609** | Built-up index - the strongest predictor available |
| `Vegetation` | -0.455 | Vegetated fraction of the cell, 0-1, from WorldCover |
| `NDVI` | -0.398 | Vegetation index |
| `Latitude` | - | Derived centroid |
| `Longitude` | - | Derived centroid |
| `LST_lag_k8` | - | *Optional set only.* Mean LST of the 8 nearest **training** cells |

`NDBI` and `Vegetation` were previously discarded by `preprocess.py`, so the
model never saw them. Restoring them is the single largest change to this
module's conclusions - see the interpretation below.

The spatial-lag feature draws neighbours from the training set only; including
test cells would leak each test cell's own target into its own feature.

## Two splits, because one of them is misleading

A random 80/20 split on a 100 m grid is optimistic: adjacent cells are near
duplicates, so nearly every held-out cell has a near-twin in training. A
**spatially blocked** split (6x6 = 36 contiguous blocks, whole blocks held out)
is reported alongside it as an honest "unseen neighbourhood" estimate.

## Results

Seed `42`, 8,144 rows, 20% held out.

| Split | Features | Model | RMSE (C) | MAE (C) | R2 |
|---|---|---|---|---|---|
| random_80_20 | base | LinearRegression | 1.0515 | 0.8083 | 0.5954 |
| random_80_20 | base | RandomForest | 0.5354 | 0.4104 | **0.8951** |
| random_80_20 | base+spatial_lag | LinearRegression | 0.3972 | 0.3023 | 0.9423 |
| random_80_20 | base+spatial_lag | RandomForest | 0.3725 | 0.2794 | 0.9492 |
| spatial_block | base | LinearRegression | 0.9342 | 0.7408 | 0.3594 |
| spatial_block | base | RandomForest | 0.8146 | 0.6411 | **0.5130** |
| spatial_block | base+spatial_lag | LinearRegression | 1.0769 | 0.8313 | 0.1489 |
| spatial_block | base+spatial_lag | RandomForest | 1.1032 | 0.8520 | 0.1068 |

Feature importances, canonical model:

| Feature | Importance |
|---|---|
| `NDBI` | 0.4081 |
| `Latitude` | 0.2635 |
| `Longitude` | 0.2202 |
| `NDVI` | 0.0742 |
| `Vegetation` | 0.0340 |

### Interpretation - quote 0.51, not 0.90

**The headline number for this model is R2 = 0.51 under spatial blocking, not
0.90 on a random split.** Same model, same features. The gap is the finding: a
random hold-out on a dense grid measures interpolation between cells the model
has already seen, not transfer to a new neighbourhood.

But the blocked score is no longer a failure. An earlier version of this module
scored **R2 = 0.15** blocked - and after a subsequent data correction, **-0.02**,
literally worse than predicting the mean. The difference is entirely the feature
set: `NDBI` alone now carries 41% of the model's importance, more than latitude
and longitude combined.

This module's own earlier "Future Improvements" list predicted exactly that,
naming land cover and NDBI as "the single most likely fix for the R2 = 0.15
generalisation failure, since built-up fraction drives surface temperature far
more than the current feature set can express." That turned out to be right. The
data had already been exported; it was being dropped in preprocessing.

Note also that `base+spatial_lag` now scores *worse* under blocking (0.11) than
plain `base` (0.51). That is the expected behaviour and a useful sanity check: a
neighbour-average feature is a gap-filler, and blocking removes the neighbours.

Honest conclusions:

- **Valid use:** estimating LST from built-up fraction, vegetation and location,
  including in parts of the city not in the training extent.
- **Not valid:** other cities, other seasons, or future dates. One Landsat
  composite is one moment - see [../docs/08-limitations.md](../docs/08-limitations.md).
- RandomForest remains the right ceiling: 8,144 rows and five features do not
  justify anything heavier.

## Saved model

`Models/heat_risk_model.pkl` holds the **base-feature RandomForest on the random
split**. Base is the only configuration valid for the real use case; the
spatial-lag variant needs neighbouring cells' *measured* LST.

The filename says `heat_risk` for continuity with the module spec, but **the
target is LST**. The artifact is a dict carrying `target`, `features`,
`random_state`, `config` and a derived `ndvi_corrected` flag, so a consumer
cannot mistake what it predicts. It is gitignored at ~170 MB; regenerate it by
re-running this script.

Nothing downstream consumes the model. The dashboard shows measured LST, and the
recommendations come from the rule engine in section 4.

---

# 4. Priority Tiering and Actions

`scripts/tier_and_recommend.py` - writes `Results/tiered.csv`,
`Results/tiering_summary.md`, `Results/priority_map.png`.

**There is no labelled ground truth for "priority" or "recommended action"
anywhere in this project.** This is an explicit rule engine, not a supervised
classifier pretending to have learned them. A classifier here would be inventing
authority it does not have.

## Priority - quantile bins on Heat_Risk

| Tier | Rule | Cutoff | Cells |
|---|---|---|---|
| Low | `Heat_Risk <= q0.25` | <= -0.324837 | 2,036 |
| Medium | between | -0.324837 to 0.039573 | 4,072 |
| High | `Heat_Risk >= q0.75` | >= 0.039573 | 2,036 |

Quantiles rather than absolute cutoffs because `Heat_Risk` is a unit-scaled
composite with no cross-city meaning. These are relative ranks within Guwahati -
by construction exactly 25% of the city is "High", however cool it is.

## Vegetation class - descriptive only

Split at an absolute **NDVI 0.3**, the literature threshold: 6,644 vegetated /
1,500 sparse.

This previously split at the dataset *median* as a deliberate workaround, because
the pre-fix NDVI had a p95 of only 0.295 and an absolute 0.3 would have labelled
the entire city sparse. With the corrected export the median is ~0.45, so
continuing to split there would have mislabelled every genuinely vegetated cell
between 0.30 and 0.45.

**This column no longer decides anything.** Suitability now comes from real land
cover rather than from an inferred vegetation index.

## The action rule - gated on land cover

Calls `shared.assign_action()`, the single implementation both this module and
Decision-Support use. In order:

1. **Water or wetland -> `None`.** A hot lake is still a lake.
2. **Already tree cover -> `None`.** No new vegetation where vegetation exists.
3. **Low priority -> `None`.**
4. **Built-up -> `Cool roof` only.** WorldCover has no road class, so a built-up
   cell may be a road; a cool roof there is moot, a park is not.
5. **Open land** (bare, grassland, cropland, shrubland) -> `Green park` if High
   priority, `Tree cover` if Medium.
6. **Unclassified -> `None`**, with the reason recorded.

The script then **asserts** no never-touch cell received an intervention rather
than trusting the rule.

> This module previously keyed its action on `(priority, vegetation_class)` with
> no land-cover input at all, because land cover did not exist upstream when it
> was written. It did once the corrected export landed - but preprocessing was
> dropping the column. The deployed dashboard consequently assigned tree planting
> or parks to 148 water and wetland cells and ground works to 3,433 built-up
> cells. The correct rule already existed in the Decision-Support module, whose
> output nothing rendered.

Why cells receive no action:

| Reason | Cells |
|---|---|
| Already vegetated (tree cover) | 3,752 |
| Never-touch land cover (water) | 149 |
| Never-touch land cover (wetland) | 44 |
| Low priority | 42 |
| **Total** | **3,987** |

That 3,752 is 46% of the study area, and it is a design decision worth revisiting
- it is defensible for *planting*, but arguable for a hot, sparsely-canopied cell
that WorldCover still labels tree cover. Tracked in [../STATUS.md](../STATUS.md).

---

# 5. Cost and Cooling

Both now come from [`shared/constants.json`](../shared/constants.json), read by
this module and by Decision-Support. They previously lived in two private copies
that happened to agree - `150 x 0.25 = 37.5 = RATE_TREE_COVER` - with nothing
enforcing it. A test does now.

```
cost_estimate = cell_area_m2 x inr_per_m2 x coverage_fraction
```

| Action | INR / m2 | Coverage | Effective INR/m2 | Assumed cooling |
|---|---|---|---|---|
| `Tree cover` | 150 | 0.25 | 37.5 | 0.8 C |
| `Cool roof` | 400 | 0.15 | 60.0 | 1.0 C |
| `Green park` | 1,150 | 0.10 | 115.0 | 2.0 C |
| `None` | 0 | 0.00 | 0 | 0 C |

`coverage_fraction` exists because treating 100% of a cell is not physically
possible - cells contain roads, buildings and water.

> **The unit rates are planning placeholders, and the cooling figures are
> assumptions, not measurements.** The cooling values originate in the
> Decision-Support catalogue, whose own comment calls them "placeholder
> engineering estimates for a hackathon demo". Nothing is fitted to Guwahati,
> validated against a field trial, or adjusted for canopy age, albedo, humidity
> or wind, and a flat per-action number ignores that cooling scales with treated
> area and with how hot a cell already is. Replace before any figure informs a
> budget.

Cell area is computed from each polygon's bounds via a local equirectangular
conversion, exact for these axis-aligned rectangles. Measured mean **8,916 m2**,
independently confirming the 89.8 m x 99.3 m geometry in the Remote Sensing
SPEC_AUDIT.

## Resulting programme

| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) |
|---|---|---|---|---|---|
| High | Cool roof | 1,770 | 28.64 | 0.281 | 946,829,805 |
| High | Green park | 74 | 28.82 | 0.277 | 75,889,420 |
| High | None | 192 | 26.06 | 0.038 | 0 |
| Medium | Cool roof | 1,724 | 27.27 | 0.396 | 922,163,533 |
| Medium | Tree cover | 589 | 27.71 | 0.472 | 196,982,433 |
| Medium | None | 1,759 | 27.11 | 0.497 | 0 |
| Low | None | 2,036 | 25.08 | 0.636 | 0 |

**Total notional programme cost: INR 2,141,865,191** (~INR 214 crore, placeholder
rates).
> **Only the `Green park` rate has a real-world comparable behind it.** It was revised from 250 to 1,150 INR/m² on 2026-08-14, anchored on Gujarat AMRUT 2.0 municipal gardens (Bhavani Garden ₹1,152/m²; Kailash Vatika ₹2,250/m²) — deliberately on the lower figure, since those are ~10,000 m² civic gardens with paths, lighting and boundary walls while this action treats ~892 m² of soft landscaping. The `Tree cover` and `Cool roof` rates are **unchanged and still unvalidated**: no directly comparable urban municipal rate was found for either. See `shared/constants.json` for the full provenance.


---

# 6. Columns Produced

`Results/tiered.csv`:

| Column | Source | Description |
|---|---|---|
| `grid_id` | passthrough | Unique cell identifier - the join key for everything |
| `LST` | passthrough | Land surface temperature, degrees C |
| `NDVI`, `NDBI`, `Vegetation` | passthrough | Spectral indices and vegetated fraction |
| `LandCover`, `land_cover` | passthrough / derived | WorldCover code and its readable label |
| `Heat_Risk` | passthrough | Normalised LST minus normalised NDVI |
| `Latitude`, `Longitude` | derived | Cell centroid |
| `priority` | derived | `High` / `Medium` / `Low` |
| `vegetation_class` | derived | `sparse` / `vegetated` at NDVI 0.3 - descriptive only |
| `recommended_action` | derived | One of the four dashboard actions |
| `exclusion_reason` | derived | Why a cell received `None` |
| `cell_area_m2` | derived | ~8,916 m2 |
| `cost_estimate` | derived | INR, placeholder rates |
| `cooling_c` | derived | Assumed drop in C - an assumption |
| `geo_json` | passthrough | Original `.geo` polygon string |

**Read this file with `keep_default_na=False`** on the string columns. `"None"`
is a real action label, and pandas' default `na_values` turns it into `NaN`. See
[../docs/07-data-contracts.md](../docs/07-data-contracts.md).

---

# 7. Frontend Integration

`scripts/export_grid_geojson.py` writes 8,144 features, 3.64 MB, to **both**
`Results/grid.geojson` and `frontend/data/grid.geojson`.

Feature properties are exactly these seven keys, no more and no fewer:

```
grid_id, temperature, ndvi, priority, recommended_action, cost_estimate, cooling_c
```

`validate()` enforces the key set, `Polygon` geometry, an `int` `cost_estimate`
(the frontend calls `.toLocaleString()`), a numeric `cooling_c` (the after-map
computes `temperature - cooling_c`), and an action from the known four. It fails
loudly rather than shipping a file the dashboard cannot render.

**Both copies are written by the same run.** Previously only the `Results/` copy
was written and somebody copied it into `frontend/data/` by hand - an
undocumented step with nothing to detect it being skipped. A test asserts the two
files are byte-identical.

No legend retuning is needed when this output changes: `frontend/js/config.js`
derives its colour domain from the 2nd/98th percentiles of whatever it loads.

---

# 8. Tools

| Package | Version | Used for |
|---|---|---|
| pandas | 3.0.5 | Tabular pipeline |
| numpy | 2.4.6 | Numerics, seeded RNG |
| scikit-learn | 1.9.0 | RandomForest, LinearRegression, NearestNeighbors, metrics |
| shapely | 2.1.2 | GeoJSON parsing, centroids, bounds |
| matplotlib | 3.11.0 | Plots (Agg backend, headless) |
| joblib | 1.5.3 | Model serialisation |
| scipy | 1.18.0 | scikit-learn dependency |

**geopandas / fiona / pyproj are deliberately not required.** The `.geo` column
is plain GeoJSON, so `shapely` + `json` cover all geometry work without the GDAL
stack.

---

# How to Run

```bash
pip install -r requirements.txt

python scripts/preprocess.py
python scripts/train_regression.py
python scripts/tier_and_recommend.py
python scripts/export_grid_geojson.py
```

Each script resolves paths relative to its own location, so the working
directory does not matter. They must run in the order above.

Tests: `pytest tests/` from the repository root. CI runs the full pipeline on
every push and fails if the regenerated outputs differ from the committed ones.

---

# Future Improvements

Ordered by how much they would change the conclusions:

1. **Validate the cooling figures.** They drive the entire "after intervention"
   map and the cost-effectiveness ranking, and nobody measured them. Even a crude
   check - do WorldCover tree-cover cells run measurably cooler than adjacent
   built-up cells? - would turn an assumption into an estimate, using data already
   committed.
2. **Multi-temporal LST.** Seasonal or diurnal composites instead of one annual
   median. Landsat also crosses mid-morning, while the urban heat island is
   typically strongest at night - which this data cannot see at all.
3. **Revisit the `already_green` exclusion**, which currently zeroes 46% of the
   study area.
4. **Validate the cost heuristics** against real municipal unit rates.
5. **Ground-truth the priority tiers** against a planner's assessment, which
   would make a supervised classifier legitimate here for the first time.

Items 1-3 of the previous edition of this list - re-run GEE with the NDVI fix,
join land cover, add NDBI - are all done, and item 2's prediction that land cover
and NDBI would fix the generalisation failure proved correct.
