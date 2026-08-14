# 07 — Data contracts

Every schema in the project: who writes it, who reads it, and what breaks if you
change it. This page exists because the two worst defects this project has had
were both contract failures that nothing detected — a file renamed without
updating its readers, and a column dropped in transit.

---

## The chain

```
dataset.csv                    written by Earth Engine, read by both Python modules
    ↓
preprocessed.csv               written by preprocess.py, read by steps 2 and 3
    ↓
tiered.csv                     written by tier_and_recommend.py, read by step 4
    ↓
grid.geojson                   written by export_grid_geojson.py, read by the browser
```

Decision-Support branches off `dataset.csv` directly and produces its own three
CSVs, which nothing else reads.

---

## Contract 1 — `dataset.csv`

**Written by** `Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js`,
run in the Earth Engine Code Editor.
**Read by** `preprocess.py` and `member3_decision_support.py`.
**Location** `Remote Sensing & Data Engineering/Dataset/dataset.csv`, 8,144 rows.

| Column | Type | Meaning |
|---|---|---|
| `grid_id` | string | Stable cell identifier, e.g. `+102031+29091`. The join key for everything. |
| `LST` | float | Land surface temperature, °C. Observed range 21.1–33.2. |
| `NDVI` | float | Vegetation index, −1..1. Observed range −0.42 to 0.78. |
| `NDBI` | float | Built-up index. The strongest single predictor of LST in this data (+0.61). |
| `Vegetation` | float | Vegetated fraction of the cell, 0..1. |
| `LandCover` | float | ESA WorldCover v200 class code (10/20/30/40/50/60/80/90). |
| `Heat_Risk` | float | `unitScale(LST, 20, 34) − unitScale(NDVI, −0.2, 0.8)`. Not an independent measurement — see below. |
| `Latitude`, `Longitude` | float | Cell centroid. |
| `.geo` | string | The cell polygon as GeoJSON. Carried through verbatim so no reprojection error is introduced. |
| `system:index`, `count` | — | Earth Engine bookkeeping. Dropped in preprocessing. |

**`Heat_Risk` is a closed-form function of `LST` and `NDVI`.** `preprocess.py`
verifies the identity holds to ~1e-15 on every row. This is why the regression
targets `LST`: predicting `Heat_Risk` from `NDVI` plus location would be
recovering an algebraic identity, not learning anything.

### The two things that break this contract

**Renaming the file.** It happened: this was `Guwahati_Urban_Heat_Dataset.csv`,
was renamed to `dataset.csv`, and both readers kept the old name — so both
crashed on a clean clone. The filename now lives in `shared/constants.json` and
is resolved through `shared.source_dataset_path()`, which raises with a
directory listing rather than a bare `FileNotFoundError`.

**Exporting without the newer columns.** `LandCover`, `NDBI` and `Vegetation`
were added by a later Earth Engine run. `preprocess.py` now refuses to run
without them, because a silently land-cover-free dataset is what produced
recommendations to plant trees in the river.

---

## Contract 2 — `preprocessed.csv`

**Written by** `preprocess.py`. **Read by** `train_regression.py` and
`tier_and_recommend.py`.

Columns: `grid_id`, `LST`, `NDVI`, `Heat_Risk`, `LandCover`, `land_cover`,
`NDBI`, `Vegetation`, `Latitude`, `Longitude`, `geo_json`.

Two changes from the source: `.geo` is renamed `geo_json`, and `land_cover` is
added as the readable label for the numeric `LandCover` code.

> **This is where the worst defect in the project lived.** This step used to
> select only seven columns and drop `LandCover`, `NDBI` and `Vegetation`. Both
> downstream consumers were therefore blind to land cover — one of them assigned
> interventions, and so assigned them to water. Both consumers now assert the
> columns are present rather than coping with their absence.

---

## Contract 3 — `tiered.csv`

**Written by** `tier_and_recommend.py`. **Read by** `export_grid_geojson.py`.

Everything in `preprocessed.csv`, plus:

| Column | Meaning |
|---|---|
| `priority` | `High` / `Medium` / `Low`, from Heat_Risk quantiles (top 25% / middle 50% / bottom 25%). |
| `vegetation_class` | `sparse` / `vegetated` at NDVI 0.3. **Descriptive only** — it does not decide the action. |
| `recommended_action` | One of `Tree cover`, `Cool roof`, `Green park`, `None`. |
| `exclusion_reason` | Why a cell got `None`. Empty when an action was assigned. |
| `cell_area_m2` | Computed from the polygon; ~8,912–8,920 m². |
| `cost_estimate` | Integer INR. `effective_rate × cell_area_m2`. |
| `cooling_c` | Assumed temperature drop, °C. **An assumption, not a measurement.** |

### The `"None"` trap

`"None"` is a real action label, not a missing value. pandas' default
`na_values` list includes the bare string `"None"`, so a naive
`pd.read_csv("tiered.csv")` turns 3,987 deliberate no-action cells into `NaN`,
and `str()` then renders them as `"nan"`. The frontend tests
`action !== 'None'` — and `"nan"` passes that test, so those cells would receive
a cooling subtraction they were explicitly marked as not needing.

Always read this file as:

```python
STRING_COLUMNS = ["grid_id", "priority", "recommended_action"]
pd.read_csv(path, keep_default_na=False,
            na_values={c: [] for c in STRING_COLUMNS})
```

---

## Contract 4 — `grid.geojson` (the frontend contract)

**Written by** `export_grid_geojson.py`, to `frontend/data/grid.geojson`.
**Read by** the browser. One file, one writer.

A `FeatureCollection`. Each feature has a `Polygon` geometry and **exactly**
these seven properties — no more, no fewer. `validate()` enforces this and
refuses to write a file that violates it.

| Property | Type | Consumed by | Breaks how if wrong |
|---|---|---|---|
| `grid_id` | string | `popup.js` | Popup shows a blank identifier. |
| `temperature` | float, 1 dp | `heatField.js`, `mapView.js`, `analytics.js` | The entire heat surface. Renamed from `LST`. |
| `ndvi` | float, 3 dp | `popup.js`, `analytics.js` | Scatter plot and popup. Renamed from `NDVI`. |
| `priority` | string | `filters.js`, `popup.js`, `analytics.js` | Filter buttons match nothing. |
| `recommended_action` | string | `compareView.js`, `popup.js` | Must be one of the four labels — `config.js` keys `INTERVENTIONS` on them. An unknown label renders a blank popup rather than raising. |
| `cost_estimate` | **int** | `popup.js` | Must be `int`: `.toLocaleString()` is called on it. |
| `cooling_c` | **numeric** | `dataLoader.js`, `compareView.js` | Must be numeric: the after-map computes `temperature − cooling_c`. A string silently produces string concatenation, not arithmetic. |

**There is one copy.** Previously only a `Results/` copy was written and somebody
moved it into `frontend/data/` by hand — an undocumented step with nothing to
detect it being skipped. It then briefly wrote both, duplicating 3.7 MB in the
repository. The dashboard's copy is the artifact, so it is the only one.

### What the browser does with it

`dataLoader.js` reduces each polygon to a centroid plus a bounding box; the
renderer never uses the full ring. It also derives the colour domain from the
2nd and 98th percentiles of the temperatures actually present, so the legend
cannot drift out of step with the data — no retuning is needed when the numbers
change.

---

## Contract 5 — the Decision-Support outputs

**Written by** `member3_decision_support.py`. **Read by** nothing automated —
these are analysis products.

| File | Rows | Contents |
|---|---|---|
| `recommendation.csv` | 4,157 | `grid_id`, `lat`, `lon`, `land_cover`, `priority`, `LST`, `NDVI`, `recommended_action`, `cost_estimate`, `cooling_c`, `cooling_per_rupee` |
| `excluded.csv` | 3,987 | `grid_id`, `lat`, `lon`, `land_cover`, `priority`, `LST`, `exclusion_reason` |
| `ranking.csv` | 4,157 | `rank`, `grid_id`, `lat`, `lon`, `recommended_action`, `cost_estimate`, `cooling_c`, `cooling_per_rupee`, `cumulative_cost`, `within_budget` |

These use `lat`/`lon` where the ML module uses `Latitude`/`Longitude`, and carry
no polygon geometry — they are point records. Turning them into a `grid.geojson`
would require re-joining to the source geometry. That is deliberate: the ML
module owns the dashboard contract, this module owns the budget question.

**Both modules produce the same action for every cell**, because both call
`shared.assign_action()`. A test asserts it. If they ever diverge, one of them
stopped using the shared rule.

---

## Contract 6 — `shared/constants.json`

**Read by** both Python modules at import. Not read by the browser — the
frontend keeps its own copy of the intervention labels and fallback cooling in
`js/config.js`, because it must render a file it did not produce.

If you change an action name here, you must change it in `js/config.js` too.
Nothing enforces that across the language boundary; the four labels are a
hand-maintained contract between Python and JavaScript, and
`export_grid_geojson.py`'s `VALID_ACTIONS` check is the tripwire.

---

## Rules of thumb

1. **Never hand-edit a generated file.** Regenerate and commit. CI diffs them.
2. **Never rename a data file without changing `shared/constants.json`.**
3. **Adding a column is safe. Removing or renaming one is not** — the frontend
   contract is exact-match on the key set.
4. **If you add an action label**, add it in three places: `shared/constants.json`,
   `frontend/js/config.js` (`INTERVENTIONS` and `ECO_ICONS`), and the tests.
5. **Read `tiered.csv` with `keep_default_na=False`** on the string columns.
