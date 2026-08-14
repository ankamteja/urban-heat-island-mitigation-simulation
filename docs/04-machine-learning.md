# 04 — Machine Learning & Prediction

The module that turns the satellite export into the map the dashboard renders.
Four scripts, run in order. Every threshold is a named constant, and every one
of them is listed here.

```bash
cd "Machine Learning & Prediction"
python scripts/preprocess.py          # step 1
python scripts/train_regression.py    # step 2  (optional for the dashboard)
python scripts/tier_and_recommend.py  # step 3
python scripts/export_grid_geojson.py # step 4
```

Steps 3 and 4 are what the dashboard depends on. Step 2 produces the model and
its metrics, which nothing downstream consumes — it answers "can we predict
temperature", not "what should we build".

---

## Step 1 — `preprocess.py`

Reads `dataset.csv`, writes `Results/preprocessed.csv`.

What it does:

1. **Validates the source.** Refuses to run if `LandCover`, `NDBI` or
   `Vegetation` are missing — their absence means you are reading a superseded
   export.
2. **Checks NDVI provenance.** An earlier Earth Engine script computed NDVI on
   raw digital numbers without the Landsat Collection 2 Level 2 rescale
   (`× 0.0000275 − 0.2`), which compressed the whole city below 0.39 and biased
   `Heat_Risk` upward. The check is *derived from the data* — `NDVI.max() > 0.5`
   — rather than hardcoded, because every script in this repository spent weeks
   printing "NDVI is UNCORRECTED" directly above a line showing a corrected
   range.
3. **Parses geometry** from the `.geo` column and derives each cell's centroid.
4. **Attaches a readable `land_cover` label** to the numeric WorldCover code.
5. **Verifies the Heat_Risk identity.** Confirms
   `Heat_Risk == unitScale(LST, 20, 34) − unitScale(NDVI, −0.2, 0.8)` holds to
   ~1e-15. This is what justifies targeting `LST` in step 2.

> The correction for a raw-DN NDVI is **not recoverable from the CSV**.
> `NDVI_wrong` depends only on the ratio of the two bands; `NDVI_correct`
> depends on their sum as well, and the sum is not exported. Two different band
> pairs that yield the same wrong 0.3333 give correct values of 0.6471 and
> 0.4400. Fixing it requires re-running the Earth Engine script.

---

## Step 2 — `train_regression.py`

Reads `Results/preprocessed.csv`, writes the model, metrics and plots.

**Target: `LST`.** Not `Heat_Risk` — see the identity above.

**Features:** `NDVI`, `NDBI`, `Vegetation`, `Latitude`, `Longitude`.

`NDBI` and `Vegetation` were previously dropped in step 1, so the model never
saw them. Measured on the current dataset:

| Feature | Correlation with LST |
|---|---|
| `NDBI` | **+0.609** |
| `Vegetation` | −0.455 |
| `NDVI` | −0.398 |

The built-up index is the strongest single predictor available, and it was being
discarded. The module used to explain the weak NDVI signal as an artifact of the
uncorrected export; the real gap was a missing feature.

### Two splits, and why only one is honest

| Split | What it measures |
|---|---|
| `random_80_20` | Scattered hold-out. On a 100 m grid, adjacent cells are near-duplicates, so almost every test cell has a near-twin in training. **Flatters the model badly.** |
| `spatial_block` | Holds out whole contiguous blocks (a 6×6 partition). Answers "how well does this generalise to a neighbourhood it has never seen". **This is the honest number.** |

Current scores for the canonical Random Forest on base features:

| Split | RMSE (°C) | MAE (°C) | R² |
|---|---|---|---|
| random_80_20 | 0.535 | 0.410 | 0.895 |
| spatial_block | 0.815 | 0.641 | **0.513** |

**Quote the spatial-block figure, or both. Never the random-split figure alone.**
Before `NDBI` and `Vegetation` were restored, the spatial-block R² was −0.02 —
literally worse than predicting the mean.

There is also a `base+spatial_lag` feature set, which adds the mean LST of the
eight nearest *training* cells. It scores higher on a random split and worse on
a blocked one, which tells you exactly what it is: a gap-filler for areas
already surveyed, not a predictor for anywhere new. It is deliberately **not**
the saved model.

---

## Step 3 — `tier_and_recommend.py`

Reads `Results/preprocessed.csv`, writes `Results/tiered.csv`, a summary and a
map. This is the rule engine, and it is deliberately not a classifier: there is
no labelled ground truth anywhere in this project for "priority" or "correct
intervention", so a supervised model here would be inventing authority it does
not have.

### Rule 1 — priority tiers

Quantile bins on `Heat_Risk`: top 25% `High`, bottom 25% `Low`, middle 50%
`Medium`. Quantiles rather than absolute cutoffs because `Heat_Risk` is a
unit-scaled composite whose absolute value carries no meaning across cities —
these are relative ranks within Guwahati, which is what a municipal
prioritisation actually needs.

### Rule 2 — vegetation class (descriptive only)

Splits at an absolute NDVI of **0.3**, the literature threshold.

This previously split at the dataset *median* — a deliberate workaround, because
the pre-fix export's NDVI had a 95th percentile of only ~0.295 and an absolute
0.3 would have labelled the whole city sparse. With the corrected export the
median is ~0.45, so continuing to split there would mislabel every genuinely
vegetated cell between 0.30 and 0.45.

**This column no longer decides anything.** Now that real land cover exists,
suitability comes from land cover rather than from an inferred vegetation index.

### Rule 3 — the action, from land cover and priority

Calls `shared.assign_action()`. In order:

1. **Water or wetland → nothing.** A hot lake is still a lake.
2. **Already tree cover → nothing.** No new vegetation where vegetation exists.
3. **Low priority → nothing.**
4. **Built-up → `Cool roof` only.** WorldCover has no road class, so a built-up
   cell may be a road; a cool roof there is moot, whereas a park is not.
5. **Open land** (bare, grassland, cropland, shrubland) → `Green park` if High
   priority, `Tree cover` if Medium.
6. **Anything unclassified → nothing**, with the reason recorded.

The script then **asserts** that no never-touch cell received an intervention,
rather than trusting the rule. This property is invisible in every aggregate the
project produces, and it was wrong in production for weeks.

> This module previously keyed its action on `(priority, vegetation_class)` with
> **no land-cover input at all**, because land cover did not exist upstream when
> it was written. It did once the corrected export landed — but step 1 was
> dropping the column. The result: 148 water and wetland cells and 3,433
> built-up cells assigned physical ground works, live on the deployed site.

### Rules 4 and 5 — cost and cooling

Both come from `shared/constants.json`.

| Action | INR/m² | Coverage | Effective INR/m² | Assumed cooling |
|---|---|---|---|---|
| Tree cover | 150 | 25% | 37.5 | 0.8 °C |
| Cool roof | 400 | 15% | 60.0 | 1.0 °C |
| Green park | 1,150 | 10% | 115.0 | 2.0 °C |
| None | 0 | 0% | 0 | 0 °C |

Coverage is the share of a ~8,916 m² cell actually treated — you cannot plant
trees over 100% of a cell that contains roads and buildings.

> **These are planning placeholders, not procured costs, and the cooling figures
> are not measurements.** They originate in the Decision-Support catalogue,
> whose own comment calls them "placeholder engineering estimates for a hackathon
> demo". Nothing is fitted to Guwahati, validated against a field trial, or
> adjusted for canopy age, albedo, humidity or wind, and a flat per-action number
> ignores that cooling scales with treated area and with how hot a cell already
> is. Replace them before any figure informs a budget.

### Current output

| Priority | Action | Cells |
|---|---|---|
| High | Cool roof | 1,770 |
| High | Green park | 74 |
| Medium | Cool roof | 1,724 |
| Medium | Tree cover | 589 |
| — | None | 3,987 |

Of the 3,987 excluded: 3,752 already tree cover, 149 water, 44 wetland, 42 low
priority.

---

## Step 4 — `export_grid_geojson.py`

Reads `Results/tiered.csv`, writes `Results/grid.geojson` **and**
`frontend/data/grid.geojson`.

Renames `LST → temperature` and `NDVI → ndvi`, rounds temperature and cooling to
1 dp and NDVI to 3, and carries the source polygon through verbatim so no
reprojection error is introduced.

`validate()` refuses to write a file the dashboard cannot render: exact property
key set, `Polygon` geometry, integer `cost_estimate` (the frontend calls
`.toLocaleString()`), numeric `cooling_c` (the after-map computes
`temperature − cooling_c`), and `recommended_action` restricted to the four
known labels. See [07 — Data contracts](./07-data-contracts.md) for the full
schema and the `"None"`/`"nan"` trap.

---

## Reproducing

Every seed is fixed (`RANDOM_STATE = 42`). The CSVs and GeoJSON regenerate
byte-identically; the PNGs do not, across matplotlib versions, so CI does not
diff them. The trained model is gitignored at ~170 MB — regenerate it with step 2.
