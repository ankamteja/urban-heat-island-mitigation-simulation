# 8. Limitations

This project documents its own weaknesses on purpose. This page is the consolidated list — the one to read before quoting any figure from this repository in a report, a pitch, or a decision.

It links rather than duplicates. The authoritative per-module detail lives in:

- [`Remote Sensing & Data Engineering/SPEC_AUDIT.md`](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md)
- [`Machine Learning & Prediction/SPEC_AUDIT.md`](../Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md)
- [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md)

---

## The one that matters most: NDVI in the committed data is wrong

**Status: fixed in source, not yet applied to data.**

The Earth Engine script originally computed NDVI directly from Landsat Collection 2 Level 2 digital numbers:

```js
image.normalizedDifference(['SR_B5','SR_B4'])
```

C2 L2 surface-reflectance bands require `× 0.0000275 − 0.2` first. The multiplier would cancel out of a normalized difference; **the `− 0.2` offset does not**. The result is a systematically compressed NDVI.

Measured across all 8,144 cells in the committed dataset:

```
NDVI   min −0.097   median 0.179   p95 0.295   max 0.386
```

A city with Guwahati's tree cover and surrounding hills should reach 0.7–0.85. Every vegetation value in this repository is too low.

`urban_heat_analysis.js` now contains the correct rescale. The committed `Guwahati_Urban_Heat_Dataset.csv` was exported before it and has **not** been regenerated, because doing so requires an Earth Engine run in an account with access to the private boundary asset `projects/urban-heat-guwahati/assets/guwahati_boundary`.

### What is contaminated by this

Everything derived from NDVI, transitively:

| Affected | How |
|---|---|
| `Heat_Risk` | Defined as `unitScale(LST) − unitScale(NDVI)`. Under-credits vegetation, so biased **high** everywhere |
| Priority tiers | Quantile bins on `Heat_Risk`. The quantile trick keeps them valid as *relative ranks within this city* but the bias is brightness-dependent and therefore not perfectly uniform, so even the ranking is approximate |
| The vegetation split in `tier_and_recommend.py` | Uses the dataset median instead of the literature threshold of 0.3, precisely because p95 is only 0.295 and an absolute 0.3 would label the entire city "sparse" |
| Both proxy land-cover classifiers | ML's and Decision-Support's quantile-based stand-ins exist only because there is no real `land_cover` column |
| The regression's NDVI signal | NDVI–LST correlation is only −0.279; the true relationship is almost certainly stronger |
| Everything the dashboard displays | `ndvi` is rendered raw in popups |

**Three separate modules built workarounds for this one line.** Fixing it upstream removes all three at once.

### After the re-run

Once the corrected dataset lands, these deliberately-conservative choices should be revisited — they are correct *for today's data* and wrong once the data is fixed:

- `tier_and_recommend.py`: switch `VEGETATION_SPLIT_QUANTILE` back to an absolute NDVI of 0.3
- `member3_decision_support.py`: set `USE_PROXY_LANDCOVER = False` to consume the real `LandCover` column, which re-enables `pocket_park` and `green_roof`
- `frontend/js/mapView.js`: re-check `TEMP_COLOR_SCALE` against the new LST distribution

Do not make these changes before the re-run.

---

## Numbers that are assumptions, not measurements

**Never present these as findings.**

### Costs

`tier_and_recommend.py`'s `COST_HEURISTICS` are order-of-magnitude planning placeholders — an INR-per-m² rate times a plausible coverage fraction times the cell's real area. No tender, survey, or municipal rate card sits behind them. The resulting "total notional programme cost" of ~₹1.6 billion is an internally-consistent way to *rank* cells by investment, and nothing more.

Decision-Support's flat per-cell costs are a **second, incompatible** set of placeholders. They disagree with ML's by 18–67× for the same intervention:

| Intervention | ML (area-based) | Decision-Support (flat) | Ratio |
|---|---|---|---|
| Trees | ₹334,350 | ₹5,000 | 66.9× |
| Cool roof | ₹534,960 | ₹30,000 | 17.8× |

**Resolution:** ML's model is authoritative for anything displayed or reported. Decision-Support's numbers are retained only because its `cooling_per_rupee` ranking depends on their ratios, not their magnitudes. The two must never appear side by side in the same document as if both were "the" cost.

### Cooling

The per-intervention cooling values (`Tree cover` 0.8 °C, `Cool roof` 1.0 °C, `Green park` 2.0 °C) originate in Decision-Support, where they are self-labelled *"placeholder engineering estimates for a hackathon demo."* They are now also used by the ML pipeline and drive the dashboard's "After Intervention" map.

They are plausible orders of magnitude from the urban-cooling literature. They are not modelled, not fitted, and not measured for Guwahati. The after-intervention map is an **illustration of a policy, not a prediction of an outcome.**

---

## Model performance is weaker than the headline number

`metrics.md` reports R² = 0.938 for the random forest — but that is under a **random** 80/20 split, on spatially autocorrelated data. Neighbouring cells are 100 m apart and nearly identical, so a random split leaks almost every test cell's answer into training via its neighbours.

The same model under a **spatial-block** split scores **R² = −0.02**: worse than predicting the mean.

| Split | Model | R² |
|---|---|---|
| random 80/20 | RandomForest + spatial lag | 0.938 |
| spatial block | RandomForest + spatial lag | −0.025 |

The honest reading: this model interpolates temperature within a neighbourhood it has already seen, and does **not** generalise to unseen parts of the city. Feature importances say the same thing — Latitude (0.489) and Longitude (0.265) together outweigh NDVI (0.246), meaning the model is substantially memorising location.

Quote the spatial-block number, or quote both. Quoting 0.938 alone overstates the result.

---

## Deliverables still missing

From the Remote Sensing module's own spec, unresolved until the Earth Engine re-run:

- `temperature.tif`, `ndvi.tif` — export code is now in the script; no run has produced them
- `grid.geojson` from GEE — likewise (the ML module produces its own, from the CSV's embedded geometry)
- Real `land_cover` and `Vegetation` columns — both proxies disappear once these exist
- NDBI — computed in the script now, absent from the committed data

## Structural caveats

**Grid cells are not square in metres.** They are 0.00089832° squares in EPSG:4326, which at latitude 26.13° is **89.8 m × 99.3 m**, not 100 × 100. Areas are computed correctly from the polygon bounds, so costs are right; but do not describe the grid as "100 m squares" in a methods section without the qualifier.

**Coverage is ~81 km², not the whole municipal area.** 8,144 cells inside a 212 km² bounding box. The geoBoundaries ADM3 polygon used is smaller than Guwahati's full municipal extent.

**A single annual median composite.** All of 2025 collapsed into one image. There is no seasonal, diurnal, or year-over-year dimension — a hot-season UHI analysis would need a different temporal filter.

**Decision-Support currently recommends exactly one intervention type.** Under proxy land cover, `trees` beats `cool_roof` on cooling-per-rupee (1.6e-4 vs 3.3e-5) in every cell where both are legal, and they are always legal together. `pocket_park` and `green_roof` are deliberately disabled under the proxy. Result: 100% of its 6,108 recommendations are `trees`. "Four intervention types" is currently one. See [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md) finding 5.

**The QGIS project's layers do not resolve.** `QGIS/guwahati_heat_project.qgz` references `./guwahati_boundary.geojson` (resolves inside `QGIS/`, where the file is not), a `.shp` that is not in the repo at all, and an absolute local `Downloads/` path. It opens with three broken layers on any clone.

---

## What is *not* a limitation

Two things that look like problems and are not:

**Median compositing for cloud removal** is what the module spec asked for, and it is what the script does. The addition of a per-pixel `QA_PIXEL` mask improves it; its earlier absence was not a spec failure.

**The tiering being a rule engine rather than a model.** There is no ground-truth label for "priority" anywhere in this project. A supervised classifier would have been a rule engine wearing a costume, with worse auditability and a fabricated accuracy score.
