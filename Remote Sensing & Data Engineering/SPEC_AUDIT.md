# Spec Compliance Audit — Remote Sensing & Data Engineering

**Audited:** 2026-08-07
**Repo:** `ankamteja/urban-heat-island-mitigation-simulation`
**Scope:** the Remote Sensing & Data Engineering module spec — *"Prepare satellite data for analysis."*

Verified by reading `GEE/urban_heat_analysis.js`, `README.md`, `Boundary/guwahati_boundary.geojson`, the internals of `QGIS/guwahati_heat_project.qgz`, and by statistically analysing all 8,144 rows of `Dataset/Guwahati_Urban_Heat_Dataset.csv`.

**Score: 8 of 16 spec items fully met, 1 met but numerically wrong, 7 missing.**

---

> ## Resolution status — updated 2026-08-14
>
> **Every fix in the "How to close the gaps" section below has since been applied to `GEE/urban_heat_analysis.js`.** The script now contains the SR rescale, the `QA_PIXEL` cloud/shadow mask, NDBI, ESA WorldCover land cover and vegetation, per-cell Latitude/Longitude, the GeoJSON grid export, both GeoTIFF exports, and the renamed CSV export.
>
> **The data has not been regenerated.** `Dataset/Guwahati_Urban_Heat_Dataset.csv` is still the pre-fix export, so every NDVI-derived figure quoted below remains true of the committed data. Closing the remaining gaps for real requires one run of the corrected script in the Earth Engine Code Editor, by someone with access to the private asset `projects/urban-heat-guwahati/assets/guwahati_boundary` — the exports land in that account's Google Drive.
>
> **Section numbers below are pre-fix.** The script grew from 12 sections to 17. Mapping for the references in this document:
>
> | This document says | Script section today |
> |---|---|
> | §2 Load Landsat | §2 (unchanged) |
> | §3 Median composite | §4 — a new §3 holds the cloud mask |
> | §4 LST | §5 |
> | §5 NDVI | §6 |
> | §6 Normalize | §9 |
> | §8 Create grid | §11 |
> | §9 Extract features | §12 |
> | §11 Export CSV | §14 — new §15/§16 hold the GeoJSON and GeoTIFF exports |
>
> The audit body is left as written, as the historical record of what was found on 2026-08-07.

---

## Summary

| # | Spec item | Status |
|---|---|---|
| 1 | Study town + boundary (GeoJSON/Shapefile) | ✅ Done |
| 2 | GEE — Land Surface Temperature (LST) | ✅ Done |
| 3 | GEE — NDVI | ⚠️ Done but numerically wrong |
| 4 | GEE — NDBI *(optional)* | ❌ Not done |
| 5 | Remove clouds/shadows/noise via median composite | ✅ Done as specified (scene-level only) |
| 6 | Divide study area into 100 m × 100 m grids | ✅ Effectively done (cells are 89.8 m × 99.3 m) |
| 7 | Feature — Latitude | ❌ Missing |
| 8 | Feature — Longitude | ❌ Missing |
| 9 | Feature — Temperature | ✅ Done |
| 10 | Feature — NDVI | ✅ Done (inherits issue #3) |
| 11 | Feature — Vegetation | ❌ Missing |
| 12 | Feature — Land Cover | ❌ Missing |
| 13 | Deliverable — `dataset.csv` | ✅ Done (renamed) |
| 14 | Deliverable — `grid.geojson` | ❌ Missing |
| 15 | Deliverable — `temperature.tif` | ❌ Missing |
| 16 | Deliverable — `ndvi.tif` | ❌ Missing |
| — | Tool — Google Earth Engine | ✅ Used |
| — | Tool — QGIS | ⚠️ Used, project file has broken layer paths |
| — | Tool — Python | ❌ Not used (zero `.py` files) |

---

## Detail

### 1. Study town + boundary — Done

`Boundary/guwahati_boundary.geojson` is a valid `FeatureCollection` with a single `MultiPolygon` feature, sourced from geoBoundaries:

```
shapeName:  Guwahati
shapeGroup: IND
shapeType:  ADM3
shapeID:    7132399B10647404007859
```

### 2. LST — Done

`GEE/urban_heat_analysis.js` §4:

```js
var lst = image.select('ST_B10')
  .multiply(0.00341802)
  .add(149.0)
  .subtract(273.15)
  .rename('LST');
```

Correct Landsat Collection 2 Level 2 thermal scale/offset, correct Kelvin→Celsius conversion. Exported values run **20.94 – 33.09 °C** (median 27.29, p99 30.15). Physically plausible for a Guwahati annual median. **No change needed.**

### 3. NDVI — Done but numerically wrong

`GEE/urban_heat_analysis.js` §5:

```js
var ndvi = image.normalizedDifference(['SR_B5','SR_B4']).rename('NDVI');
```

This runs on **raw DN values**. Landsat C2 L2 surface-reflectance bands require `× 0.0000275 − 0.2` before use. The multiplier alone would cancel out in a normalized difference — but the **`− 0.2` offset does not**, so the ratio is distorted.

Worked example: raw `SR_B5 = 20000`, `SR_B4 = 10000`.

| | NIR | RED | NDVI |
|---|---|---|---|
| Raw DN (current code) | 20000 | 10000 | **0.333** |
| Correctly rescaled | 0.350 | 0.075 | **0.647** |

Empirical confirmation across all 8,144 exported cells:

```
NDVI   min -0.097   median 0.179   p95 0.295   p99 0.331   max 0.386
```

Maximum NDVI of **0.386** is not credible for a city with Guwahati's tree cover and surrounding hills — healthy vegetation should reach 0.7–0.85. Every NDVI value is compressed toward zero.

**Knock-on effect:** `Heat_Risk = unitScale(LST, 20, 34) − unitScale(NDVI, −0.2, 0.8)` is computed from this NDVI, so the entire `Heat_Risk` column is biased high (vegetation is systematically under-credited). The heat-risk map in `Results/` inherits the same bias.

### 4. NDBI — Not done

No use of `SR_B6` (SWIR1) anywhere in the script. Marked optional in the spec.

### 5. Cloud / shadow / noise removal — Done as specified

The spec asks for removal "using median composite", and the script does exactly that:

```js
.filter(ee.Filter.lt('CLOUD_COVER', 20))   // §2
var image = landsat.median();              // §3
```

**Met.** One quality note, not a spec failure: `CLOUD_COVER` is a **scene-level** metadata filter. A scene at 19% cloud is admitted whole, clouded pixels included. Adding a per-pixel `QA_PIXEL` bitmask before the median would be strictly better — see snippet B.

### 6. 100 m grid — Effectively done

`GEE/urban_heat_analysis.js` §8 builds the grid by vectorizing a random image at 100 m scale. Verified from the exported geometries:

- 8,144 cells, **every one** with `count = 1` (one 100 m pixel per cell — no accidental merging)
- Uniform cell size, exactly `0.00089832°` square in EPSG:4326
- At latitude 26.13° that is **89.8 m east–west × 99.3 m north–south**

So cells are ~100 m but not square *in metres*, because the grid is defined in degrees, not a projected CRS. Fine for most analysis; note it if you compute per-cell densities or areas. To get true 100 m squares, build the grid in a metric CRS (e.g. UTM 46N, `EPSG:32646`).

Coverage: bounding box 18.0 × 11.8 km (212 km²); 8,144 cells ≈ 81 km² of actual polygon area. Consistent with the ADM3 boundary being smaller than its bbox.

### 7–12. Per-grid features

Actual CSV columns:

```
system:index, Heat_Risk, LST, NDVI, count, grid_id, .geo
```

| Spec feature | Present? | Note |
|---|---|---|
| Latitude | ❌ | Geometry is only in the `.geo` polygon column; no scalar lat |
| Longitude | ❌ | Same |
| Temperature | ✅ | `LST`, zero nulls across 8,144 rows |
| NDVI | ✅ | `NDVI`, zero nulls — but see #3 |
| Vegetation | ❌ | No vegetation class or fraction field. NDVI is a proxy, not this field |
| Land Cover | ❌ | No land-cover dataset joined at all |

`Heat_Risk` is an extra beyond spec.

### 13–16. Deliverables

| Deliverable | Status |
|---|---|
| `dataset.csv` | ✅ Present as `Dataset/Guwahati_Urban_Heat_Dataset.csv` — 8,144 rows, no nulls. Only the filename differs from spec |
| `grid.geojson` | ❌ Never exported. Grid polygons exist **only** embedded in the CSV's `.geo` column |
| `temperature.tif` | ❌ The script contains only `Export.table.toDrive` (§11). There is no `Export.image.toDrive` anywhere |
| `ndvi.tif` | ❌ Same |

### Tools

- **Google Earth Engine** ✅ — `GEE/urban_heat_analysis.js`, complete 12-section workflow.
- **QGIS** ⚠️ — `QGIS/guwahati_heat_project.qgz` opens, but its layer datasources do not resolve:
  ```
  ./guwahati_boundary.geojson      → resolves inside QGIS/, file actually lives in Boundary/
  ./guwahati_boundary.shp          → no .shp exists anywhere in the repo
  ../../../Downloads/geoBoundaries-IND-ADM3-all/geoBoundaries-IND-ADM3.geojson
                                   → a local Downloads path, not portable
  ```
  These were already broken before the repo restructure — the folder move did not cause them. Anyone cloning this repo gets three unresolved layers. Fix by relinking to `../Boundary/guwahati_boundary.geojson` and re-saving the project.
- **Python** ❌ — no `.py` files. Listed in the spec's tool set but unused.

---

## How to close the gaps

Items 4, 7, 8, 11, 12, 14, 15, 16 and the NDVI fix all require a Google Earth Engine run — exports go to *your* Google Drive, and the script depends on the private asset `projects/urban-heat-guwahati/assets/guwahati_boundary`. Snippets below are drop-in replacements for the matching sections of `GEE/urban_heat_analysis.js`.

### A. Fix NDVI — rescale surface reflectance first

Replace §5:

```js
// Landsat C2 L2 surface reflectance -> physical reflectance
var sr = image.select(['SR_B4','SR_B5','SR_B6'])
              .multiply(0.0000275)
              .add(-0.2);

var ndvi = sr.normalizedDifference(['SR_B5','SR_B4']).rename('NDVI');
var ndvi_guwahati = ndvi.clip(guwahati);
```

After this, expected NDVI range is roughly −0.1 to 0.85. You will also need to re-tune the `unitScale` bounds in §6 (`ndvi_norm`) — `unitScale(-0.2, 0.8)` becomes correct rather than over-wide.

### B. Per-pixel cloud and shadow mask

Insert before §3, and change `landsat.median()` to `landsat.map(maskL8).median()`:

```js
function maskL8(img) {
  var qa = img.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(1 << 1).eq(0)   // dilated cloud
    .and(qa.bitwiseAnd(1 << 2).eq(0))      // cirrus
    .and(qa.bitwiseAnd(1 << 3).eq(0))      // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));     // cloud shadow
  return img.updateMask(mask);
}
```

### C. NDBI

```js
var ndbi = sr.normalizedDifference(['SR_B6','SR_B5']).rename('NDBI');
var ndbi_guwahati = ndbi.clip(guwahati);
```

### D. Land cover + vegetation fraction

```js
var worldcover = ee.ImageCollection('ESA/WorldCover/v200').first()
                   .select('Map').rename('LandCover').clip(guwahati);

// binary vegetation: WorldCover classes 10 (tree), 20 (shrub), 30 (grass), 40 (crop)
var vegetation = worldcover.remap([10,20,30,40], [1,1,1,1], 0).rename('Vegetation');
```

In §9, add per-cell reducers — `Reducer.mode()` for `LandCover` (it is categorical, mean is meaningless) and `Reducer.mean()` for `Vegetation` (giving vegetated fraction of the cell).

### E. Latitude / Longitude columns

Inside the §9 `map` function, before the `return`:

```js
var c = cell.geometry().centroid(1).coordinates();
```

then add to the `cell.set({...})` call:

```js
'Longitude': c.get(0),
'Latitude':  c.get(1),
```

### F. Export `grid.geojson`

```js
Export.table.toDrive({
  collection: grid_dataset,
  description: 'grid',
  fileFormat: 'GeoJSON'
});
```

### G. Export `temperature.tif` and `ndvi.tif`

```js
Export.image.toDrive({
  image: lst_guwahati,
  description: 'temperature',
  region: guwahati.geometry(),
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
});

Export.image.toDrive({
  image: ndvi_guwahati,
  description: 'ndvi',
  region: guwahati.geometry(),
  scale: 30,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF'
});
```

### H. Rename the dataset deliverable

Spec names it `dataset.csv`. Either change `description: 'Guwahati_Urban_Heat_Dataset'` to `'dataset'` in §11, or keep the descriptive name and note the mapping — your call.

---

## Suggested order

1. **A** (NDVI rescale) — everything downstream is wrong until this lands.
2. **B** (cloud mask), then re-run and sanity-check that max NDVI now reaches ~0.8.
3. **E**, **C**, **D** — new feature columns.
4. **F**, **G**, **H** — exports; commit the four deliverables back to `Dataset/`.
5. Relink the QGIS project layers to `../Boundary/guwahati_boundary.geojson` and re-save.
