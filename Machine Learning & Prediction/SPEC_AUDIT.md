# Spec Compliance Audit - Machine Learning & Prediction

**Audited:** 2026-08-12
**Repo:** `ankamteja/urban-heat-island-mitigation-simulation`
**Scope:** the Machine Learning & Prediction module spec - *"Turn the grid dataset into
mitigation guidance."*

Self-audit written in the same form as the
[Remote Sensing SPEC_AUDIT](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md),
covering what this module delivers, what it deliberately declines to deliver, and what
it cannot deliver from the available inputs.

**Score: 12 of 13 spec items fully met, 1 met by documented exception.**

---

## Summary

| # | Spec item | Status |
|---|---|---|
| 1 | Module folder mirroring RS module structure | Met |
| 2 | Parse `.geo` into real geometries | Met |
| 3 | Derive Latitude / Longitude from centroids | Met - closes RS gaps #7/#8 |
| 4 | Handle the NDVI defect explicitly | Met by exception - correction is non-invertible |
| 5 | Drop `system:index` and `count`, keep `grid_id` | Met |
| 6 | Regression model with justified target | Met - target LST, justification below |
| 7 | RandomForest vs LinearRegression baseline | Met |
| 8 | Optional spatial-lag feature | Met - leak-free, train-only neighbours |
| 9 | 80/20 split, fixed seed, RMSE + R2 table | Met - plus a spatial-block split |
| 10 | Save model to `Models/heat_risk_model.pkl` | Met - filename kept, target is LST |
| 11 | Rule engine, not a fake supervised classifier | Met |
| 12 | Cost from real cell area, documented constants | Met |
| 13 | `grid.geojson` with exactly the frontend's 6 keys | Met - verified against mock |
| - | Guardrail: no changes to RS module or GEE script | Held - module is purely additive |
| - | Guardrail: no silent frontend data swap | Held - diff documented, not applied |
| - | Guardrail: fixed seeds, pinned versions | Held |

---

## Detail

### 4. The NDVI defect - met by documented exception

The spec offered two routes: **(a)** correct NDVI inline during preprocessing, or
**(b)** proceed with the biased column and state the caveat prominently.

**Route (a) is mathematically impossible from the exported CSV.** This is a finding,
not a preference.

The GEE script computes:

```js
image.normalizedDifference(['SR_B5','SR_B4'])   // on raw DN
```

Let `D = DN_nir - DN_red`, `S = DN_nir + DN_red`, and let `s = 0.0000275`,
`o = -0.2` be the Landsat C2 L2 scale and offset. Then:

```
NDVI_wrong   = D / S                        depends on the DN ratio only
NDVI_correct = s*D / (s*S + 2*o)            depends on the DN sum as well
```

The multiplier `s` cancels in a normalised difference, but the offset `o` does not -
and `S` was never exported. So `NDVI_wrong` does not determine `NDVI_correct`.
Demonstration - three band pairs, one shared wrong value:

| Raw NIR | Raw RED | `NDVI_wrong` | `NDVI_correct` |
|---|---|---|---|
| 20000 | 10000 | 0.3333 | 0.6471 |
| 40000 | 20000 | 0.3333 | 0.4400 |
| 12000 | 6000 | 0.3333 | 1.7368 (physically degenerate) |

The first two rows are both plausible urban Landsat pixels and differ by **0.21 NDVI**
- larger than the entire observed range of the exported column. The third exceeds
NDVI's valid `[-1, 1]` range, illustrating that low-DN pixels drive the denominator
toward zero after the offset is applied; it is not a realistic surface but it bounds
the sensitivity.

Route (b) was therefore taken, with disclosure at four levels:

1. A dedicated **READ THIS FIRST** section at the top of `README.md`.
2. A block comment in `preprocess.py` at the point where NDVI passes through
   uncorrected, carrying the same worked example.
3. Runtime `WARNING:` lines printed by `preprocess.py`, `train_regression.py`, and
   `tier_and_recommend.py`.
4. `ndvi_corrected: False` plus a `caveat` string embedded in the saved model artifact,
   so a downstream consumer loading the `.pkl` cannot miss it.

**Double-correction hazard: none.** This module applies no correction of its own, so
fixing item A upstream in the GEE script and re-exporting is safe. The pipeline reads
whatever `NDVI` column it is handed and needs no code change to consume a corrected
export - only `VEGETATION_SPLIT_QUANTILE` in `tier_and_recommend.py` should be
revisited (README section 4).

### 6. Target choice - LST, not Heat_Risk

`preprocess.py` verifies across all 8,144 rows:

```
Heat_Risk == (LST - 20)/14 - (NDVI + 0.2)
max |residual| = 1.41e-15
```

`Heat_Risk` is a closed-form function of `LST` and `NDVI`. Since `NDVI` is a model
feature, regressing `Heat_Risk` on it would recover an algebraic identity rather than
learn anything - the model would rediscover the `-1` coefficient on the NDVI term and
leave `LST` as the residual. `LST` is the independently measured quantity, and it is
what the dashboard renders as `temperature`.

### 8-9. Splits and leakage - one addition beyond spec

The spec asked for a random 80/20 split with a fixed seed. That is implemented and
reported as specified. A **spatially blocked** split (6x6 = 36 contiguous blocks) is
reported alongside it, because the random split materially overstates performance on
this data:

| Configuration | Random 80/20 R2 | Spatial block R2 |
|---|---|---|
| RandomForest, base | **0.9010** | **0.1510** |
| LinearRegression, base | 0.2475 | -0.6136 |
| RandomForest, base+lag | 0.9379 | -0.0245 |
| LinearRegression, base+lag | 0.9337 | -0.0624 |

On a 100 m grid, adjacent cells are near duplicates, so a random split hands the model
a near-twin of almost every test cell. The 0.90 is largely spatial memorisation of
lat/lon. Under blocking the same model scores 0.15, and both linear variants go
negative - worse than predicting the mean.

Reporting only the random-split figure would have been misleading, so **README section
3 states R2 = 0.15 as the headline** and explains the collapse.

Two leakage controls are in place:

- The spatial-lag feature draws neighbours **only from the training set**
  (`NearestNeighbors` is fitted on train coordinates). Test cells never contribute to
  their own feature. Self-matches are dropped when querying training rows.
- kNN operates in a local metric projection, not raw degrees, so that neighbour
  distances are not distorted by the ~10:1 anisotropy between a degree of longitude
  and a degree of latitude at this latitude.

### 10. Saved artifact

`Models/heat_risk_model.pkl` keeps the spec's filename while the target is `LST`. To
prevent that mismatch from misleading a consumer, the artifact is a dict carrying
`target`, `features`, `trained_on`, `random_state`, `config`, `ndvi_corrected`, and
`caveat` alongside the estimator - not a bare estimator.

The **base-feature** model is saved rather than the better-scoring spatial-lag variant,
because only the base set matches the real use case. The lag feature requires
neighbouring cells' *measured* LST, so it can only gap-fill inside an already-surveyed
area.

### 11. Rule engine, not a classifier

No labelled `priority` or `recommended_action` ground truth exists in this project.
Training a classifier on synthesised labels would have produced a model that appeared
validated while only reproducing its own rules. Tiers are quantile bins on `Heat_Risk`;
actions come from an explicit six-row `(priority, vegetation_class)` table; both are
named constants at the top of `tier_and_recommend.py` and reproduced in README section 4.

One consequence worth flagging: the `High / vegetated` combination captures only **81
of 8,144 cells**, because high `Heat_Risk` almost requires low NDVI by construction.
The `Cool roof` action is therefore rare in the output - correct given the rules, but
it means that branch is thinly exercised.

### 12. Cost estimates

`cost_estimate = cell_area_m2 x inr_per_m2 x coverage_fraction`, with all six constants
declared in `COST_HEURISTICS` under a comment stating they are planning placeholders
rather than fitted or tendered costs.

Cell area is computed from each polygon's own bounds. Measured mean **8,916 m2**
independently reproduces the 89.8 m x 99.3 m geometry reported in Remote Sensing
SPEC_AUDIT item #6 (89.8 x 99.3 = 8,917 m2).

### 13. Frontend contract

`Results/grid.geojson` was diffed against `frontend/mock_data/grid.geojson`:

```
mock props: cost_estimate, grid_id, ndvi, priority, recommended_action, temperature
real props: cost_estimate, grid_id, ndvi, priority, recommended_action, temperature
EXACT MATCH: True
```

`export_grid_geojson.py` re-validates this key set on every feature at write time and
raises rather than emitting a file the dashboard cannot render. It also asserts
`cost_estimate` is an `int`, since `popup.js` calls `.toLocaleString()` on it.

---

## Issues this module surfaces elsewhere

Neither is a defect in this module; both are recorded so they are not lost.

### A. The frontend temperature legend is calibrated for the wrong range

`frontend/js/mapView.js` buckets `TEMP_COLOR_SCALE` at 30 / 34 / 38 C. Real LST spans
**20.9 to 33.1 C**, so:

| Legend band | Share of the 8,144 real cells |
|---|---|
| `< 30 C` | **98.6%** |
| `30-34 C` | 1.4% |
| `34-38 C` | **0.0% - band never used** |
| `> 38 C` | **0.0% - band never used** |

Half the legend is dead, and 98.6% of cells collapse into a single colour, leaving the
choropleth effectively flat.

The mock data ran 28-42 C, which is why this was not visible before. Suggested
real-data buckets: 25 / 27.5 / 30 / above. `renderHeatLayer` is unaffected - it
min-max normalises its own intensities.

### B. Cell count rises 9x

The dashboard was built against 900 mock cells; the real grid has **8,144**. The
invisible `renderGridLayer` polygons exist only for popup hit-testing, so if pan/zoom
drags, `L.geoJSON(..., { renderer: L.canvas() })` is the fix.

---

## Not done

| Item | Why |
|---|---|
| Land cover / NDBI features | Require a GEE re-run (RS SPEC_AUDIT #4, #11, #12). These are the most likely fix for the R2 = 0.15 generalisation failure |
| Corrected NDVI | Non-invertible here - see item 4 |
| Multi-temporal modelling | Source is a single annual median composite |
| Validated cost rates | Needs municipal unit-rate data |
| Supervised priority classifier | Needs planner-labelled ground truth to be legitimate |
