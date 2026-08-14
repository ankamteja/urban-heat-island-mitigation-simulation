# 7. Data contracts

Nine files in this project are read by code that did not write them, and this page describes every column of every one of them. It is a reference: look up the file you are about to read or write, find the column you care about, and the table tells you its type, its unit, the range actually observed in the committed data, and what it means. Every number below was measured from the files in this repository, not estimated. Where a file has a trap in it — a JSON document hidden inside a CSV cell, a column that is always the same value, a string that pandas silently converts to a missing value — the trap gets its own paragraph.

Only three of the nine cross an actual module boundary; the rest are handoffs between scripts inside one module, or standalone deliverables. If you want the *shape* of the pipeline rather than the schemas, read [`01-architecture.md`](./01-architecture.md) first — it names those three and explains why they are the ones that matter. If you want to know which of these numbers are measurements and which are assumptions, that is [`08-limitations.md`](./08-limitations.md), and this page deliberately does not repeat it.

## Contents

- [Vocabulary](#vocabulary)
- [The join key: `grid_id`](#the-join-key-grid_id)
- [File map](#file-map)
- [1. `Guwahati_Urban_Heat_Dataset.csv`](#1-guwahati_urban_heat_datasetcsv)
- [2. `preprocessed.csv`](#2-preprocessedcsv)
- [3. `tiered.csv`](#3-tieredcsv)
- [4. `grid.geojson`](#4-gridgeojson)
- [5. The frontend contract](#5-the-frontend-contract)
- [6. The two `grid.geojson` files](#6-the-two-gridgeojson-files)
- [7. Decision-Support outputs](#7-decision-support-outputs)
- [8. If you change a column name](#8-if-you-change-a-column-name)

---

## Vocabulary

Six terms are used throughout. No GIS background is assumed.

**GeoJSON** — a way of writing geographic shapes as ordinary JSON. It is just JSON: objects, arrays, numbers, strings. Any JSON parser reads it. The specification only fixes what certain keys mean.

**FeatureCollection** — the top-level GeoJSON container. An object with `"type": "FeatureCollection"` and a `"features"` array. Each entry in that array is a *Feature*: an object carrying a `geometry` (where the thing is) and a `properties` object (everything else you know about it). A Feature is one row of a table plus a shape.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[91.652, 26.131], "..."]] },
      "properties": { "grid_id": "+102027+29089", "temperature": 27.7 }
    }
  ]
}
```

**Polygon** — a geometry type: a closed shape given as a list of rings, each ring a list of `[longitude, latitude]` pairs. The first and last pair of a ring are identical, which is how the ring closes. Ring one is the outer boundary; any further rings would be holes. Every polygon in this project is a rectangle: one ring, five points (four corners plus the repeat of the first).

**EPSG:4326** — the coordinate system these numbers are in. Plain longitude and latitude in decimal degrees on the WGS 84 globe, longitude first. EPSG:4326 is not a flat map: one degree of latitude is a fixed ~110.6 km, but one degree of longitude shrinks as you move away from the equator. That is why the grid cells in this project are square in degrees and *not* square in metres — see the `cell_area_m2` column of [`tiered.csv`](#3-tieredcsv).

**Centroid** — the geometric centre of a shape. For the axis-aligned rectangles here it is simply the midpoint of the bounding box. `preprocess.py` computes one per cell so downstream code has a single `(Latitude, Longitude)` point to work with instead of a four-corner polygon.

**Categorical vs continuous column** — a *continuous* column holds a measurement that can take any value in a range (`LST`, `NDVI`); asking for its minimum and maximum is meaningful. A *categorical* column holds a label drawn from a small fixed set (`priority`, `recommended_action`); asking for its minimum is meaningless, so the tables below give the complete value set and how many rows carry each value. The distinction matters practically: the frontend branches on categorical values by exact string comparison, so a renamed category is a silent behaviour change, whereas a shifted continuous range is at worst a mis-coloured map.

**Join key** — the column that lets you match a row in one file to the row describing the same thing in another file. Here it is `grid_id`, and it is the same string in all nine files.

---

## The join key: `grid_id`

Every file on this page is keyed on `grid_id`, and it is stable end to end: the string that leaves Earth Engine is the string the browser prints in a popup.

In the real pipeline it looks like `+102027+29089` — always 13 characters, two signed six-digit integers concatenated. These are Earth Engine's internal feature identifiers, not coordinates, so do not try to parse a position out of them. In the committed dataset all **8,144** values are distinct, so `grid_id` is a genuine primary key.

The one file that uses a different format is `frontend/mock_data/grid.geojson`, where IDs look like `91.7300_26.1500` — a `lon_lat` pair. Mock IDs and real IDs therefore never collide, which is convenient: if you see an underscore in a `grid_id`, you are looking at synthetic data.

---

## File map

| # | File | Produced by | Consumed by | Rows / features | Size on disk |
|---|---|---|---|---|---|
| 1 | [`Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv`](../Remote%20Sensing%20%26%20Data%20Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv) | `urban_heat_analysis.js` in Earth Engine | `preprocess.py`, `member3_decision_support.py` | 8,144 rows | 2,806,561 B (2.68 MiB) |
| 2 | [`Machine Learning & Prediction/Results/preprocessed.csv`](../Machine%20Learning%20%26%20Prediction/Results/preprocessed.csv) | `preprocess.py` | `train_regression.py`, `tier_and_recommend.py` | 8,144 rows | 2,957,882 B (2.82 MiB) |
| 3 | [`Machine Learning & Prediction/Results/tiered.csv`](../Machine%20Learning%20%26%20Prediction/Results/tiered.csv) | `tier_and_recommend.py` | `export_grid_geojson.py` | 8,144 rows | 3,373,468 B (3.22 MiB) |
| 4 | [`Machine Learning & Prediction/Results/grid.geojson`](../Machine%20Learning%20%26%20Prediction/Results/grid.geojson) | `export_grid_geojson.py` | copied to `frontend/data/` | 8,144 features | 3,836,933 B (3.66 MiB) |
| 5 | [`frontend/data/grid.geojson`](../frontend/data/grid.geojson) | a manual copy of #4 | `frontend/js/*.js` | 8,144 features | 3,836,933 B (3.66 MiB) |
| 6 | [`frontend/mock_data/grid.geojson`](../frontend/mock_data/grid.geojson) | `generate_mock.py` | `frontend/js/*.js`, only if you point it there | 900 features | 325,473 B (0.31 MiB) |
| 7 | [`Decision-Support/recommendation.csv`](../Decision-Support/recommendation.csv) | `member3_decision_support.py` | nothing in this repo | 6,108 rows | 598,233 B (584 KiB) |
| 8 | [`Decision-Support/ranking.csv`](../Decision-Support/ranking.csv) | `member3_decision_support.py` | nothing in this repo | 6,108 rows | 591,342 B (578 KiB) |
| 9 | [`Decision-Support/excluded.csv`](../Decision-Support/excluded.csv) | `member3_decision_support.py` | nothing in this repo | 2,036 rows | 235,948 B (230 KiB) |

Files 1–5 form one chain, each step preserving all 8,144 cells. Files 7–9 are a parallel branch off file 1 and partition the same 8,144 cells into 6,108 + 2,036.

---

## 1. `Guwahati_Urban_Heat_Dataset.csv`

**Produced by** the Earth Engine script [`urban_heat_analysis.js`](../Remote%20Sensing%20%26%20Data%20Engineering/GEE/urban_heat_analysis.js), via `Export.table.toDrive`, then downloaded and committed by hand.
**Consumed independently by** [`preprocess.py`](../Machine%20Learning%20%26%20Prediction/scripts/preprocess.py) and [`member3_decision_support.py`](../Decision-Support/member3_decision_support.py). Neither knows about the other.
**8,144 rows, 7 columns, 2,806,561 bytes.** No nulls in any column.

| Column | Type | Unit | Observed range / value set | Meaning |
|---|---|---|---|---|
| `system:index` | string | — | 8,144 distinct, e.g. `+102027+29089` | Earth Engine's own row identifier. Byte-for-byte identical to `grid_id` in all 8,144 rows |
| `Heat_Risk` | float, continuous | dimensionless index | −0.338125 to 0.652939 (median 0.137804) | Composite heat-risk score. Higher is worse. **Not an independent measurement** — see below |
| `LST` | float, continuous | °C | 20.939218 to 33.092897 (median 27.291523, p99 30.15) | Land Surface Temperature: the temperature of the ground itself as seen from orbit, not air temperature. Mean of the 30 m Landsat pixels falling in the cell |
| `NDVI` | float, continuous | dimensionless, −1 to 1 | −0.096921 to 0.386438 (median 0.179546) | Normalised Difference Vegetation Index — a greenness measure. **Systematically too low in this file**; see [`08-limitations.md`](./08-limitations.md) |
| `count` | integer, categorical in practice | pixels | always `1` (8,144 of 8,144 rows) | Pixel count from the grid-building reducer. Explained below |
| `grid_id` | string | — | 8,144 distinct values, all 13 characters | The join key |
| `.geo` | string containing JSON | — | one GeoJSON Polygon per row | The cell's outline. Explained below |

### `Heat_Risk` is a formula, not a measurement

Section 6 of the Earth Engine script defines it as

```text
Heat_Risk = unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)
```

that is, `(LST − 20) / 14 − (NDVI + 0.2) / 1.0`. Recomputing that from the `LST` and `NDVI` columns of this very file and comparing against the stored `Heat_Risk` gives a maximum absolute difference of **1.4 × 10⁻¹⁵** across all 8,144 rows — floating-point noise. `Heat_Risk` carries no information that `LST` and `NDVI` do not already carry. `preprocess.py` re-checks this identity on every run (`verify_heat_risk_identity`), and it is the reason `train_regression.py` predicts `LST` rather than `Heat_Risk`: regressing on `Heat_Risk` would be partly regressing a feature on itself.

### `.geo` is a JSON document inside a CSV cell

This is the single most surprising thing about the file. The `.geo` column does not hold a number or a label — it holds a complete GeoJSON geometry serialised as a string, with its internal double quotes CSV-escaped by doubling. One cell, unescaped, reads:

```json
{"geodesic": false,
 "type": "Polygon",
 "coordinates": [[[91.65241349286242, 26.131093299752763],
                  [91.65331180814654, 26.131093299752763],
                  [91.65331180814654, 26.13199161503688],
                  [91.65241349286242, 26.13199161503688],
                  [91.65241349286242, 26.131093299752763]]]}
```

Three things follow.

1. **You must parse it yourself.** `pd.read_csv` gives you a Python string. Both consumers call `json.loads` and then `shapely.geometry.shape` on the result.
2. **The column name starts with a dot.** In pandas you must write `df[".geo"]`; `df..geo` is a syntax error and there is no attribute-style access for it. This is why `preprocess.py` renames it to `geo_json` the moment it has read it.
3. **`geodesic` is not a GeoJSON key.** It is an Earth Engine extension meaning "treat these edges as straight lines in the coordinate plane rather than great-circle arcs". The GeoJSON specification does not define it, and every parser this project uses — `shapely`, `json`, Leaflet — ignores unknown members and reads the geometry correctly anyway. It is carried through, untouched, all the way into `grid.geojson`.

Each ring has five points because the rectangle's first corner is repeated to close it, and the box is `0.00089832°` on each side. Because that is degrees and not metres, and because a degree of longitude is shorter than a degree of latitude at Guwahati's latitude of ~26.1°, the cells are about 89.8 m × 99.3 m rather than the 100 m × 100 m the grid was nominally built at.

### `count` is always 1

Section 11 of the Earth Engine script builds the grid by taking a random image, quantising it, and calling `reduceToVectors(..., scale: 100, reducer: ee.Reducer.countEvery())`. At 100 m resolution each output polygon corresponds to a single pixel of that random image, and `countEvery()` counts the pixels behind each polygon — so the answer is `1`, 8,144 times. The column is an artefact of how the grid was constructed and tells you nothing about the data. `preprocess.py` drops it, along with `system:index`, in `DROP_COLUMNS`.

### `system:index` duplicates `grid_id`

The script sets `'grid_id': feature.id()` while Earth Engine independently writes the same feature ID into `system:index` on export. Verified: the two columns are equal in every one of the 8,144 rows. Keep `grid_id`; it is the name the rest of the project uses. `preprocess.py` drops `system:index`.

---

## 2. `preprocessed.csv`

**Produced by** [`preprocess.py`](../Machine%20Learning%20%26%20Prediction/scripts/preprocess.py).
**Consumed by** [`train_regression.py`](../Machine%20Learning%20%26%20Prediction/scripts/train_regression.py) and [`tier_and_recommend.py`](../Machine%20Learning%20%26%20Prediction/scripts/tier_and_recommend.py).
**8,144 rows, 7 columns, 2,957,882 bytes.** No nulls — `preprocess.py` raises if any appear.

This step is deliberately almost a no-op on values. It drops two useless columns, renames `.geo`, adds two derived columns, and fixes the column order. Nothing is rescaled, filtered, or corrected.

| Column | Type | Unit | Observed range / value set | Meaning |
|---|---|---|---|---|
| `grid_id` | string | — | 8,144 distinct | Join key, unchanged from file 1 |
| `LST` | float, continuous | °C | 20.939218 to 33.092897 | Unchanged from file 1 |
| `NDVI` | float, continuous | index | −0.096921 to 0.386438 | Unchanged from file 1, **including its known bias** |
| `Heat_Risk` | float, continuous | index | −0.338125 to 0.652939 | Unchanged from file 1 |
| `Latitude` | float, continuous | degrees N (EPSG:4326) | 26.101898 to 26.207899 | **New.** Latitude of the cell's polygon centroid |
| `Longitude` | float, continuous | degrees E (EPSG:4326) | 91.652863 to 91.831627 | **New.** Longitude of the cell's polygon centroid |
| `geo_json` | string containing JSON | — | one Polygon per row | `.geo` from file 1, renamed, byte-for-byte identical content |

Two things are worth knowing.

**`Latitude`/`Longitude` are the centroids, not the corners.** The polygon extends about 0.00045° beyond each of these values in every direction, so the extreme *corner* of the grid lies slightly outside the ranges above.

**`geo_json` is kept as an unparsed string on purpose.** `preprocess.py` parses the geometry to compute centroids and then throws the parsed object away, writing the original text back out. The comment in the script gives the reason: re-serialising a shapely geometry would round-trip the coordinates through a different float formatter and could change the last digits. Keeping the string means the polygons that reach the browser are bit-identical to the ones Earth Engine exported.

Note also what is *not* here: the NDVI correction. `preprocess.py` explains at length why it cannot be applied downstream — the correction depends on the raw band sum, which is not in the exported CSV, so it is mathematically non-invertible from this file and needs an Earth Engine re-run instead.

---

## 3. `tiered.csv`

**Produced by** [`tier_and_recommend.py`](../Machine%20Learning%20%26%20Prediction/scripts/tier_and_recommend.py).
**Consumed by** [`export_grid_geojson.py`](../Machine%20Learning%20%26%20Prediction/scripts/export_grid_geojson.py).
**8,144 rows, 13 columns, 3,373,468 bytes.**

The first seven columns are `preprocessed.csv` verbatim. Six are appended, in this order, by a rule engine — not a model. There is no ground-truth label for "priority" anywhere in this project, so nothing here was learned; every threshold is a named constant in the script.

| Column | Type | Unit | Observed range / value set | Meaning |
|---|---|---|---|---|
| `grid_id` … `geo_json` | — | — | as file 2 | Carried through unchanged |
| `priority` | string, **categorical** | — | `High` 2,036 · `Medium` 4,072 · `Low` 2,036 | Quartile bin on `Heat_Risk`: bottom 25% Low, top 25% High, middle 50% Medium. Applied cutoffs on this data: Low ≤ 0.005661, High ≥ 0.241290 |
| `vegetation_class` | string, **categorical** | — | `sparse` 4,072 · `vegetated` 4,072 | `NDVI` below the dataset median (0.179546) is `sparse`, at or above is `vegetated`. A median split guarantees the exact 50/50 count |
| `recommended_action` | string, **categorical** | — | `Green park` 4,072 · `None` 2,036 · `Tree cover` 1,955 · `Cool roof` 81 | Lookup on the `(priority, vegetation_class)` pair. The four values are fixed by the frontend |
| `cell_area_m2` | float, continuous | m² | 8,911.93 to 8,920.03 (mean 8,915.73) | The cell's real ground area, from its polygon bounds with a local degrees-to-metres conversion. Not 10,000 — see [EPSG:4326](#vocabulary) |
| `cost_estimate` | integer, continuous | INR (₹) | 0 to 535,177 (total 1,604,626,620) | `cell_area_m2 × rate per m² × coverage fraction`, rounded. A planning placeholder |
| `cooling_c` | float, **categorical in practice** | °C | `0.0` · `0.8` · `1.0` · `2.0` | Assumed temperature drop if the recommended action is carried out. One flat value per action |

The last three columns are entirely determined by `recommended_action` (and, for cost, by the cell's area), which makes the joint table small enough to print in full:

| `recommended_action` | Cells | `cost_estimate` range | `cooling_c` |
|---|---|---|---|
| `Tree cover` | 1,955 | 334,241 – 334,496 | 0.8 |
| `Cool roof` | 81 | 534,926 – 535,177 | 1.0 |
| `Green park` | 4,072 | 222,803 – 222,999 | 2.0 |
| `None` | 2,036 | 0 – 0 | 0.0 |

The cost range inside each action is narrow because the only thing varying is the cell's area, which varies by less than 0.1%.

### The `"None"` trap

`recommended_action` holds the literal four-character string `None` for the 2,036 cells that need no intervention. That is a real label, not a missing value — but pandas does not know that. `"None"` is in `pandas.read_csv`'s default `na_values` list, so a plain read turns all 2,036 of them into `NaN`:

```python
>>> pd.read_csv("tiered.csv")["recommended_action"].isna().sum()
2036
```

The consequences of not noticing this are not cosmetic. `str(nan)` is `"nan"`, so a naive export writes the string `"nan"` into `grid.geojson`. The browser then evaluates `action !== 'None'` in `compareView.js`, `"nan"` passes, and every one of those 2,036 explicitly-no-action cells has a cooling subtraction applied on the "After Intervention" map — while the popup reads `Suggested: nan`. `export_grid_geojson.py` records in its own comments that a previously committed `grid.geojson` had exactly this defect.

The fix, in `export_grid_geojson.py`, is to disable default NA parsing and re-enable it selectively so the numeric columns are unaffected:

```python
STRING_COLUMNS = ["grid_id", "priority", "recommended_action"]

df = pd.read_csv(
    INPUT_CSV,
    keep_default_na=False,
    na_values={c: [] for c in STRING_COLUMNS},
)
```

Any new reader of `tiered.csv` needs the same treatment.

---

## 4. `grid.geojson`

**Produced by** [`export_grid_geojson.py`](../Machine%20Learning%20%26%20Prediction/scripts/export_grid_geojson.py) into `Machine Learning & Prediction/Results/`.
**Consumed by** the frontend, after being copied to `frontend/data/`.
**8,144 features, 3,836,933 bytes.** The two copies are byte-identical (same MD5).

The top level is a FeatureCollection with exactly two keys and nothing else:

```json
{ "type": "FeatureCollection", "features": [ "... 8144 features ..." ] }
```

Each feature has `type`, `geometry`, `properties`, and its geometry is the `geo_json` string from `tiered.csv` parsed straight back into an object — same coordinates, same five-point ring, same non-standard `geodesic: false` member. All 8,144 geometries are single-ring Polygons.

A complete feature, formatted for reading (the file itself is minified, one line):

```json
{
  "type": "Feature",
  "geometry": {
    "geodesic": false,
    "type": "Polygon",
    "coordinates": [[[91.65241349286242, 26.131093299752763],
                     [91.65331180814654, 26.131093299752763],
                     [91.65331180814654, 26.13199161503688],
                     [91.65241349286242, 26.13199161503688],
                     [91.65241349286242, 26.131093299752763]]]
  },
  "properties": {
    "grid_id": "+102027+29089",
    "temperature": 27.7,
    "ndvi": 0.246,
    "priority": "Medium",
    "recommended_action": "Green park",
    "cost_estimate": 222944,
    "cooling_c": 2.0
  }
}
```

Every feature carries these seven property keys and no others — verified across all 8,144.

| Property | JSON type | Unit | Observed range / value set | Source column | Meaning |
|---|---|---|---|---|---|
| `grid_id` | string | — | 8,144 distinct | `grid_id` | Join key |
| `temperature` | number (float) | °C | 20.9 to 33.1 | `LST`, **renamed** | Land surface temperature, rounded to 1 dp |
| `ndvi` | number (float) | index | −0.097 to 0.386 | `NDVI`, **renamed** | Greenness, rounded to 3 dp. Still uncorrected |
| `priority` | string, categorical | — | `High` 2,036 · `Medium` 4,072 · `Low` 2,036 | `priority` | Tier |
| `recommended_action` | string, categorical | — | `Green park` 4,072 · `None` 2,036 · `Tree cover` 1,955 · `Cool roof` 81 | `recommended_action` | Suggested intervention |
| `cost_estimate` | number (**int**) | INR (₹) | 0 to 535,177 | `cost_estimate` | Placeholder cost |
| `cooling_c` | number (float) | °C | 0.0 · 0.8 · 1.0 · 2.0 | `cooling_c` | Assumed cooling, rounded to 1 dp |

Two renames happen here and only here: `LST` → `temperature`, `NDVI` → `ndvi`. Six columns of `tiered.csv` are dropped: `Heat_Risk`, `Latitude`, `Longitude`, `geo_json` (it becomes the geometry), `vegetation_class`, and `cell_area_m2`. The rounding is chosen to match what is displayed: `popup.js` prints `temperature` verbatim, so exporting more decimals than the popup shows would only inflate the file.

Confirming the earlier defect is gone: `recommended_action` in the committed file takes exactly the four legal values and the string `"nan"` appears zero times.

---

## 5. The frontend contract

This is the one contract in the project with an automated gate on it, and the gate is worth understanding because the failures it prevents are all *silent in the browser*.

### The seven properties and who reads each

| Property | Read by | Used how |
|---|---|---|
| `grid_id` | `popup.js` | Printed as the popup heading |
| `temperature` | `mapView.js`, `popup.js`, `compareView.js` | Chooses the fill colour, printed in the popup, and the left operand of the after-intervention subtraction |
| `ndvi` | `popup.js` | Printed verbatim |
| `priority` | `popup.js`, `filters.js` | Printed; and compared by exact string against the `data-priority` attribute of each filter button |
| `recommended_action` | `popup.js`, `compareView.js` | Printed; and tested with `action !== 'None'` to decide whether a cell gets cooled |
| `cost_estimate` | `popup.js` | `props.cost_estimate.toLocaleString()`, prefixed with `₹` |
| `cooling_c` | `compareView.js` | The right operand of the subtraction |

The whole after-intervention map is these four lines of [`compareView.js`](../frontend/js/compareView.js):

```javascript
if (action && action !== 'None' && typeof temp === 'number') {
  f.properties.temperature = +(temp - cooling).toFixed(1);
}
```

### The `validate()` gate

`export_grid_geojson.py` refuses to write the file unless every feature passes five checks. The docstring's framing is "fail loudly rather than ship a file the dashboard cannot render".

| Check | Rejects |
|---|---|
| `features` is non-empty | An empty or unreadable input CSV |
| Property key set is exactly the seven above | A missing property, or a stray extra one |
| `geometry["type"] == "Polygon"` | A Point, LineString, or MultiPolygon that Leaflet would draw wrongly |
| `isinstance(cost_estimate, int)` | A float or a string where the browser expects an integer |
| `isinstance(cooling_c, (int, float))` | A string where the browser expects a number |
| `recommended_action in VALID_ACTIONS` | Any label the frontend does not branch on |

### Why the type checks exist

These are not stylistic. Each one prevents a specific JavaScript behaviour that produces wrong output without producing an error.

**`cost_estimate` must be an `int`.** `popup.js` calls `.toLocaleString()` on it to render `₹222,944` with thousands separators. It guards with `typeof props.cost_estimate === 'number'` and falls back to `'N/A'` otherwise — so a string cost does not crash the page, it just makes every popup in the city read `Est. cost: N/A`. Nothing in the console, nothing in the network tab, just a quietly useless field. The `int` cast is what makes that guard pass.

**`cooling_c` must be numeric.** `compareView.js` computes `temp - cooling`, but it never reaches the subtraction with a bad value, because it screens first:

```javascript
const cooling = typeof rawCooling === 'number' && !isNaN(rawCooling)
  ? rawCooling
  : FALLBACK_COOLING_C;   // 3
```

A string `cooling_c` is `typeof "2.0" === 'string'`, so it fails the guard and the cell silently falls through to the flat 3 °C fallback meant for the legacy mock file. The consequence is not an error and not a blank map: **every treated cell gets cooled by 3 °C instead of its own 0.8 / 1.0 / 2.0**, overstating the effect of all three actions at once, on an "After Intervention" map that looks entirely plausible. Exactly like the `cost_estimate` case, the type check exists because the browser degrades quietly rather than failing.

**`VALID_ACTIONS` is the string-comparison check.**

```python
VALID_ACTIONS = frozenset({"Tree cover", "Cool roof", "Green park", "None"})
```

This exists to catch the `"nan"` bug documented in [`tiered.csv`](#the-none-trap). `compareView.js` decides whether to apply cooling with `action !== 'None'`. Any label that is not literally `None` — `"nan"`, `"none"`, `"No action"`, a renamed action — passes that test, and those cells get cooled on the after map despite being marked as needing nothing. Nothing throws. The map simply shows a city that gets cooler than the recommendations say it would. `VALID_ACTIONS` turns that into a pipeline crash. It is also a change detector: if someone adds a fifth action to `ACTION_TABLE` in `tier_and_recommend.py` without teaching the frontend about it, the export fails rather than shipping a value the browser has no branch for.

### What `validate()` does not check

Worth knowing before you rely on it. It does not verify that `grid_id` values are unique, that coordinates fall inside Guwahati or even inside valid longitude/latitude bounds, that polygon rings are closed, that `priority` is one of the three tier names the filter buttons use, or that `temperature` and `ndvi` are numbers. Those hold in the committed file, but by construction, not by enforcement.

---

## 6. The two `grid.geojson` files

There are two files with this name and they are not variants of each other.

| | `frontend/data/grid.geojson` | `frontend/mock_data/grid.geojson` |
|---|---|---|
| Origin | Byte-identical copy of the ML module's `Results/grid.geojson` | Generated by [`generate_mock.py`](../frontend/mock_data/generate_mock.py) with `random.uniform` / `random.choice` |
| Features | 8,144 | 900 |
| Size | 3,836,933 B | 325,473 B |
| Properties per feature | 7 | **6 — no `cooling_c`** |
| `grid_id` format | `+102027+29089` | `91.7300_26.1500` |
| Coverage | lon 91.6528–91.8316, lat 26.1019–26.2079 | lon 91.73–91.76, lat 26.15–26.18 |
| Cell size | 0.00089832° | 0.001° |
| `temperature` | 20.9 – 33.1 °C (real LST) | 28.0 – 42.0 °C (uniform random) |
| `ndvi` | −0.097 – 0.386 | −0.1 – 0.8 (uniform random) |
| `cost_estimate` | 0 – 535,177, derived from area and action | 5,108 – 199,846, uniform random |
| `priority` | High 2,036 · Medium 4,072 · Low 2,036 | High 267 · Medium 319 · Low 314 |
| `recommended_action` | Green park 4,072 · None 2,036 · Tree cover 1,955 · Cool roof 81 | Tree cover 227 · Green park 229 · Cool roof 222 · None 222 |
| Extra top-level keys | none | `"name": "grid"` and a `crs` member naming `urn:ogc:def:crs:OGC:1.3:CRS84` |
| Geometry extras | `geodesic: false` on every polygon | none |

`main.js` loads `data/grid.geojson`; switching to the mock is a one-line change to that path.

### The practical consequences

**The mock has no `cooling_c`, so the after-intervention map is a different calculation.** `compareView.js` carries a fallback for exactly this reason:

```javascript
const FALLBACK_COOLING_C = 3;
```

On real data every cell supplies its own 0.0 / 0.8 / 1.0 / 2.0. On mock data every treated cell is cooled by a flat 3 °C — larger than any real value, and applied uniformly regardless of the action. Anything you conclude about the after map while running on mock data does not transfer.

**The mock's temperatures fall outside the legend's tuned range.** `mapView.js` buckets at 24 / 27 / 30 °C, retuned to the real 20.9–33.1 °C distribution. The mock's minimum is 28.0 °C, so its lowest two colour bands are never used and almost the entire mock map renders in the top red band. A legend change that looks correct on mock data can be badly wrong on real data, and vice versa.

**The mock is a legacy schema, not a reduced one.** It predates `cooling_c` and `export_grid_geojson.py`'s `validate()` gate; nothing regenerates it as part of the pipeline, and `export_grid_geojson.py` explicitly does not touch it. If you add an eighth property to the contract, the mock will not have it, and the frontend must keep tolerating its absence — which is why every property read in `popup.js` is written with a `??` fallback.

---

## 7. Decision-Support outputs

**All three produced by** [`member3_decision_support.py`](../Decision-Support/member3_decision_support.py), which reads file 1 directly and does not touch anything the ML module produces.
**Consumed by nothing in this repository.** Searching the Python, JavaScript, and HTML sources for these filenames finds only the script that writes them. They are standalone deliverables; the dashboard does not read them.

`recommendation.csv` (6,108 rows) and `excluded.csv` (2,036 rows) partition all 8,144 cells. `ranking.csv` is `recommendation.csv` sorted and annotated — same 6,108 cells, same join key.

Two renames happen on load, and they apply to all three files: `LST` → `predicted_temp` and `NDVI` → `ndvi`. `predicted_temp` is a misleading name: nothing is predicted. It is the measured `LST` column of file 1, renamed because the script was written expecting a model output that never arrived. Its range across `recommendation.csv` is exactly `LST`'s range, 20.939218 to 33.092897.

### `recommendation.csv` — 6,108 rows, 8 columns, 598,233 bytes

| Column | Type | Unit | Observed range / value set | Meaning |
|---|---|---|---|---|
| `grid_id` | string | — | 6,108 distinct | Join key |
| `lat` | float, continuous | degrees N | 26.102796 to 26.207001 | Polygon centroid latitude, computed here independently of `preprocess.py` |
| `lon` | float, continuous | degrees E | 91.652863 to 91.831627 | Polygon centroid longitude |
| `land_cover` | string, categorical | — | `bare_or_built_hot`, `moderate` (2 of 3 possible values) | **Proxy** land cover from NDVI quartiles, not real land-cover data |
| `predicted_temp` | float, continuous | °C | 20.939218 to 33.092897 | `LST`, renamed. Measured, not predicted |
| `intervention` | string, categorical | — | `trees` — **all 6,108 rows** | Best option by cooling-per-rupee |
| `cost_rupees` | float, continuous | INR (₹) | 5,000.0 in every row | Flat per-cell placeholder cost. **Not** the ML module's area-based cost |
| `cooling_c` | float | °C | 0.8 in every row | Assumed cooling for `trees` |

### `excluded.csv` — 2,036 rows, 6 columns, 235,948 bytes

Cells for which no intervention was legal. Recorded rather than dropped, on purpose.

| Column | Type | Unit | Observed range / value set | Meaning |
|---|---|---|---|---|
| `grid_id` | string | — | 2,036 distinct | Join key |
| `lat` | float, continuous | degrees N | 26.101898 to 26.207899 | Centroid latitude |
| `lon` | float, continuous | degrees E | 91.652863 to 91.831627 | Centroid longitude |
| `land_cover` | string, categorical | — | `vegetated` — all 2,036 rows | The third proxy class |
| `predicted_temp` | float, continuous | °C | 22.409563 to 31.327461 | `LST`, renamed |
| `exclusion_reason` | string, categorical | — | `already vegetated - no action needed` — all 2,036 rows | Why the cell has no recommendation |

The script also has a "never touch" path for roads, highways, water, and wetlands, which would write a second `exclusion_reason` value. It never fires on this data: the proxy classifier only ever emits `vegetated`, `moderate`, or `bare_or_built_hot`, and none of those is in `NEVER_TOUCH`. Every exclusion in the committed file is the vegetated one.

### `ranking.csv` — 6,108 rows, 10 columns, 591,342 bytes

`recommendation.csv` sorted descending by `cooling_per_rupee`, with a running budget applied.

| Column | Type | Unit | Observed range / value set | Meaning |
|---|---|---|---|---|
| `rank` | integer, continuous | — | 1 to 6,108 | Position in the greedy order. Unique |
| `grid_id` | string | — | 6,108 distinct | Join key |
| `lat` | float, continuous | degrees N | 26.102796 to 26.207001 | Centroid latitude |
| `lon` | float, continuous | degrees E | 91.652863 to 91.831627 | Centroid longitude |
| `intervention` | string, categorical | — | `trees` — all rows | As `recommendation.csv` |
| `cost_rupees` | float, continuous | INR (₹) | 5,000.0 in every row | As `recommendation.csv` |
| `cooling_c` | float | °C | 0.8 in every row | As `recommendation.csv` |
| `cooling_per_rupee` | float, continuous | °C per ₹ | **0.00016 in every row — one distinct value** | The ranking score |
| `cumulative_cost` | float, continuous | INR (₹) | 5,000 to 30,540,000 | Running sum of `cost_rupees` down the ranking |
| `within_budget` | boolean | — | `True` 1,000 · `False` 5,108 | Whether `cumulative_cost` is still under the ₹5,000,000 budget |

Two facts about this file that are only visible in the data.

**`cooling_per_rupee` has exactly one distinct value.** It is `0.8 / 5000 = 0.00016`, and the intended tie-breaker never engages. The script computes `heat_priority_boost = 1 + max(0, predicted_temp - 35) * 0.02`, but the hottest cell in the dataset is 33.09 °C, so `max(0, ...)` is zero and the boost is exactly `1.0` for all 8,144 cells. The "slightly favour hotter cells" logic is dead code on this data. With every score tied, `sort_values` is stable and preserves input order, so `rank` follows the source CSV's row order — which is spatial. **The ranking is not meaningfully prioritised.**

**`within_budget` is a straight prefix.** ₹5,000,000 budget ÷ ₹5,000 per cell = the first 1,000 rows exactly, and because the ranking is arbitrary, those 1,000 cells are the first 1,000 in spatial order rather than the 1,000 best.

The rupee figures in these three files are **not** the project's authoritative costs. That is `COST_HEURISTICS` in `tier_and_recommend.py`; see [`08-limitations.md`](./08-limitations.md) for why the two models disagree and why they must never be quoted side by side.

---

## 8. If you change a column name

Nothing in this project auto-discovers schemas. Every rename has to be made by hand in every file that mentions the name, and the only automated safety net is `validate()` in `export_grid_geojson.py`, which sees only the last hop. Work in the order given — each step's output is the next step's input.

### Renaming a source column (e.g. `LST` → something else)

The name appears in six places before it reaches the browser.

1. `Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js` — the property name set on each feature before export. Requires an Earth Engine re-run.
2. Re-export and re-commit `Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv`.
3. `Machine Learning & Prediction/scripts/preprocess.py` — the required-column check in `load_source()`, the `verify_heat_risk_identity()` formula, and the explicit column order in `main()`.
4. `Machine Learning & Prediction/scripts/train_regression.py` — the regression target and feature list.
5. `Machine Learning & Prediction/scripts/tier_and_recommend.py` — every reference in the rule engine and the summary `groupby`.
6. `Decision-Support/member3_decision_support.py` — the `rename` call in `load_data()`, which maps `LST` → `predicted_temp` independently of the ML module. **This is the one people forget**: it reads the source CSV directly and shares no code with the ML pipeline.

Then re-run `preprocess.py`, `train_regression.py`, `tier_and_recommend.py`, `export_grid_geojson.py`, `member3_decision_support.py`, and copy `grid.geojson` to `frontend/data/`.

If the renamed source column is one the export maps to a frontend property, `validate()` will catch a mistake at step 6. If it is `Heat_Risk`, `Latitude`, or `Longitude` — none of which reach the frontend — nothing will catch it.

### Renaming a frontend property (e.g. `cooling_c` → `delta_c`)

These four files must change in the same commit. There is no fallback and no deprecation path.

1. `Machine Learning & Prediction/scripts/export_grid_geojson.py` — the `FRONTEND_PROPERTIES` list *and* the key in `build_feature()`. They are written separately; changing only one makes `validate()` fail immediately, which is the intended behaviour.
2. `frontend/js/` — whichever files read it, from the [table above](#the-seven-properties-and-who-reads-each). `temperature` touches three files; `cooling_c` touches only `compareView.js`.
3. `frontend/mock_data/generate_mock.py` and the committed `frontend/mock_data/grid.geojson`, or accept that the mock silently falls into the frontend's `??` / fallback branches.
4. Regenerate `grid.geojson` and copy it to `frontend/data/`. The old copy has the old key and the dashboard reads the copy, not the original.

If the property is `priority`, also change the `data-priority` attributes on the filter buttons in `frontend/index.html` — `filters.js` compares them to the property by exact string.

### Adding a new per-cell field

1. `Machine Learning & Prediction/scripts/tier_and_recommend.py` — compute it and append it to the output frame. Append at the end; the existing column order in `tiered.csv` is treated as stable.
2. Re-run `tier_and_recommend.py`.
3. `Machine Learning & Prediction/scripts/export_grid_geojson.py` — add the key to `FRONTEND_PROPERTIES` *and* to `build_feature()`, with an explicit cast (`int(...)` or `float(...)`) matching what the browser will do with it. **Skipping this step is not optional**: `validate()` compares key sets for equality, so a field present in `build_feature()` but absent from `FRONTEND_PROPERTIES`, or vice versa, hard-fails the export.
4. Add a type check to `validate()` if the browser will do arithmetic on it or call a number method on it. That is the whole reason the `cost_estimate` and `cooling_c` checks exist.
5. `frontend/js/popup.js` (or wherever it is displayed) — read it with a `??` fallback so `mock_data/grid.geojson`, which will not have the field, still renders.
6. Regenerate and copy `grid.geojson` to `frontend/data/`.

If the new field is a categorical one the frontend branches on, add a `VALID_*` frozenset check alongside `VALID_ACTIONS`. String comparisons in JavaScript fail silently; that is the lesson the existing check encodes.

---

Every caveat about *whether these numbers should be believed* — the NDVI bias that contaminates `Heat_Risk`, the tiers and both proxy land-cover classifiers, the two incompatible cost models, the assumed cooling values, and the regression's true out-of-sample performance — is collected in [`08-limitations.md`](./08-limitations.md). Read it before quoting any figure from this page.
