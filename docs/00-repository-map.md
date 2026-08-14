# 00 — Repository map

What every folder and file in this repository is, who writes it, and who reads
it. If you are looking at a filename and wondering whether you can change it,
this is the page.

Two things are worth knowing before the table:

- **Some files are hand-written source; others are generated.** Editing a
  generated file is always wrong — it will be silently overwritten the next
  time the pipeline runs, and CI will fail because the committed copy no longer
  matches what the pipeline produces. Every row below says which it is.
- **Data flows in one direction**, from satellite export to dashboard. Nothing
  downstream ever writes back upstream.

---

## The one-paragraph version

Google Earth Engine measures Guwahati and exports one CSV of 8,144 grid cells
(`Remote Sensing & Data Engineering/Dataset/dataset.csv`). That file is the
single source of truth. Two Python modules read it independently — one produces
the map the dashboard renders, the other produces a budget-ranked shortlist —
and both get their rules and constants from `shared/`. The browser reads exactly
one file, `frontend/data/grid.geojson`, and nothing else.

---

## Top level

| Path | Kind | What it is |
|---|---|---|
| `README.md` | source | Project front page: quick start, module table, what the project claims. |
| `STATUS.md` | source | The current state of the project — what works, what is assumed, what is still open. The one document to trust about status; it replaced five overlapping audit files that had drifted out of date. |
| `LICENSE` | source | MIT for the source, plus attribution terms for geoBoundaries, Landsat, ESA WorldCover and OpenStreetMap, which carry their own licences. |
| `index.html` | source | The public landing page (the thing at the root of the deployed site). Static; links through to the dashboard. Not the dashboard itself. |
| `vercel.json` | source | Deployment config: a `/dashboard` redirect and a one-day cache header on `frontend/data/*`. |
| `.vercelignore` | source | Keeps the analysis modules out of the deployment. Only the dashboard needs to ship; the ML module alone is ~180 MB with a trained model. |
| `.gitignore` | source | Excludes the trained model (~170 MB, over GitHub's blob limit and fully regenerable) and Python bytecode. |

---

## `shared/` — the single definition of every cross-module rule

Added because the two Python modules each kept private copies of the same
constants, and one of those copies was missing the land-cover safety rule. The
result was a dashboard that recommended planting trees on open water.

| Path | Kind | What it is |
|---|---|---|
| `shared/constants.json` | source | Unit rates, cooling assumptions, the ESA WorldCover code→label map, which land covers may receive which intervention, tier cut points, the budget, and the dataset filename. **Change a number here and both modules change together.** |
| `shared/uhi_shared.py` | source | The loader plus the functions both modules call: `source_dataset_path()`, `land_cover_label()`, `assign_action()` (the suitability rule), `action_cost()`, `action_cooling_c()`, `ndvi_looks_corrected()`. |

`assign_action()` is the most important function in the repository. It decides
what may be built where, and it is the reason no intervention is ever assigned
to water, wetland, or an already-forested cell.

---

## `Remote Sensing & Data Engineering/` — the upstream stage

Produces the dataset everything else consumes. Runs in the Earth Engine Code
Editor in a browser, not on your machine.

| Path | Kind | What it is |
|---|---|---|
| `GEE/urban_heat_analysis.js` | source | **The canonical Earth Engine script.** Builds the 100 m grid, computes land surface temperature, NDVI, NDBI and vegetation fraction from Landsat 8, joins ESA WorldCover land cover, and exports the result. Everything in this project traces back to this file. |
| `Dataset/dataset.csv` | generated (by hand, via Earth Engine) | The 8,144-cell export. **The single source of truth, and the one artefact that cannot be regenerated without a Google Earth Engine account.** Columns: `grid_id`, `LST`, `NDVI`, `NDBI`, `Vegetation`, `LandCover`, `Heat_Risk`, `Latitude`, `Longitude`, `.geo`. |
| `Boundary/guwahati_boundary.geojson` | source | The study-area outline used to clip every raster. |
| `Results/temperature.tif`, `Results/ndvi.tif` | generated | Raster exports from the same script — for GIS work, not read by any code here. |
| `QGIS/guwahati_heat_project.qgz` | source | A QGIS project for inspecting the rasters. Known issue: it references layers by paths that no longer resolve — see `STATUS.md`. |
| `README.md`, `SPEC_AUDIT.md` | source | Module documentation and its spec-by-spec self-assessment. |

---

## `Machine Learning & Prediction/` — modelling, tiering, and the dashboard's data

The module that feeds the dashboard. Run its four scripts in order.

| Path | Kind | What it is |
|---|---|---|
| `scripts/preprocess.py` | source | **Step 1.** Reads `dataset.csv`, parses the polygon geometry, derives cell centroids, attaches a readable `land_cover` label, and writes a tidy table. Carries `LandCover`, `NDBI` and `Vegetation` forward — it used to drop them, which is what blinded the rule engine. |
| `scripts/train_regression.py` | source | **Step 2.** Fits Linear Regression and Random Forest against LST under two feature sets and two train/test splits. Writes metrics and plots, saves one canonical model. Read the spatial-block score, not the random-split one. |
| `scripts/tier_and_recommend.py` | source | **Step 3.** Assigns each cell a priority tier from its Heat_Risk quantile, then an action via the shared suitability rule, then a cost and an assumed cooling. Asserts that no never-touch cell received an intervention. |
| `scripts/export_grid_geojson.py` | source | **Step 4.** Emits the GeoJSON the dashboard renders, validates every feature against the frontend's contract, and writes it to `frontend/data/grid.geojson` - the single copy. |
| `Results/preprocessed.csv` | generated, gitignored | Output of step 1, input to steps 2 and 3. A pure intermediate: 3.3 MB, regenerated in seconds, read by nothing else. |
| `Results/tiered.csv` | generated | Output of step 3 — every cell with its tier, action, cost and cooling. The most useful file for analysis. |
| `Results/metrics.md`, `Results/metrics.json` | generated | Model scores under both splits. |
| `Results/tiering_summary.md` | generated | Cell counts, land-cover breakdown, why cells were excluded, total programme cost. |
| `Results/pred_vs_actual.png`, `feature_importances.png`, `priority_map.png` | generated | Plots. Not byte-reproducible across matplotlib versions, so CI does not diff them. |
| `Models/heat_risk_model.pkl` | generated, gitignored | The trained Random Forest, ~170 MB. Regenerate with step 2. |
| `requirements.txt` | source | Pinned dependencies for the whole Python side. |
| `README.md`, `SPEC_AUDIT.md` | source | Module documentation. |

---

## `Decision-Support/` — budget-constrained prioritisation

Answers a different question from the ML module: not "what should each cell
get" but "given a fixed budget, which cells do we actually fund first".

| Path | Kind | What it is |
|---|---|---|
| `member3_decision_support.py` | source | Reads `dataset.csv` directly, applies the same shared suitability rule and the same tier cut points, then ranks every actionable cell by cooling per rupee and marks how far the budget reaches. |
| `recommendation.csv` | generated | Every actionable cell with its action, cost and assumed cooling. |
| `excluded.csv` | generated | Every cell that gets nothing, **with the reason** — water, already forested, or low priority. The audit trail for the safety rule. |
| `ranking.csv` | generated | The same cells ordered by cost-effectiveness, with a running cumulative cost and a `within_budget` flag. |
| `README.md` | source | Module documentation. |

Because both modules now share one rule, their per-cell actions are identical.
The ML module owns geometry and the dashboard contract; this module owns the
budget question. Neither is "the" engine.

---

## `frontend/` — the dashboard

Plain HTML, CSS and JavaScript. No build step, no bundler, no `package.json` —
open it over HTTP and it runs. Libraries load from CDNs at pinned versions.

| Path | Kind | What it is |
|---|---|---|
| `index.html` | source | The dashboard page: layout, panels, and the script tags. |
| `style.css` | source | All styling. |
| `data/grid.geojson` | generated | **The only data file the browser loads.** Written by the ML module's step 4. |
| `js/main.js` | source | Bootstrap: loads the grid, then wires up every other module. Start reading here. |
| `js/config.js` | source | The colour ramp, the intervention catalogue (labels, glyph colours, fallback cooling), priority colours, and currency formatting. The temperature domain is derived from the data's 2nd/98th percentiles at load time, so the legend cannot drift out of step with the data. |
| `js/dataLoader.js` | source | Fetches the GeoJSON and reduces each polygon to the flat record the renderer uses. Also computes the summary statistics behind every KPI. |
| `js/heatField.js` | source | The heat surface. Splats each cell into two float accumulators (weight, weight×temperature) and divides per pixel, so colour means degrees rather than density. Uses a separable running-sum box blur — constant cost per pixel regardless of radius. The most substantial code in the project. |
| `js/mapView.js` | source | Leaflet setup, basemap tiles, the legend, and keeping the two map panes in sync without a feedback loop. |
| `js/compareView.js` | source | Orchestrates the before/after panes, area selection, and the prediction reveal. |
| `js/selection.js` | source | Drag-a-box area selection on the map. |
| `js/filters.js` | source | The priority filter buttons. |
| `js/analytics.js` | source | The KPI cards and the four Chart.js panels. |
| `js/popup.js` | source | The per-cell popup markup. |
| `js/ecology.js` | source | Derives illustrative planting sites within a selection and renders their markers. |
| `README.md` | source | Frontend documentation, including the data contract. |

---

## `backend/` — the automated data refresh

| Path | Kind | What it is |
|---|---|---|
| `backend/refresh_dataset.py` | source | Re-measures every committed grid cell from Earth Engine headlessly, against a service account, and rewrites `dataset.csv`. **Deliberately does not regenerate the grid** — it recomputes over the existing cell polygons so `grid_id` stays stable and every downstream join keeps working. |
| `backend/requirements.txt` | source | The Earth Engine client, on top of the ML module's dependencies. |

Driven by `.github/workflows/refresh-data.yml` monthly. See [09 — Automated refresh](./09-automated-refresh.md).

---

## `tests/` — what stops this from happening again

| Path | Kind | What it is |
|---|---|---|
| `tests/test_suitability.py` | source | The rules in isolation: nothing is ever built on water or wetland, built-up land never receives ground work, open land never receives a roof, unknown actions raise instead of silently becoming NaN. |
| `tests/test_pipeline_integration.py` | source | The committed artefacts against each other: the dashboard grid is neither stale nor unsafe, both modules agree cell by cell, costs match the shared rate table, and the two copies of `grid.geojson` are identical. |

Run them with `pytest tests/` from the repository root.

---

## `docs/` — the guides

| Path | What it covers |
|---|---|
| `docs/README.md` | Index and suggested reading order. |
| `docs/00-repository-map.md` | This page. |
| `docs/01-architecture.md` | The modules, the data flow, and the seams between them. |
| `docs/02-setup-and-build.md` | Clean clone to running dashboard. |
| `docs/03-remote-sensing.md` | The Earth Engine script, section by section. |
| `docs/04-machine-learning.md` | The four ML scripts and every threshold they apply. |
| `docs/05-decision-support.md` | The ranking module and the budget model. |
| `docs/06-frontend.md` | The dashboard's files and rendering approach. |
| `docs/07-data-contracts.md` | Every schema, who writes it, who reads it, and what breaks if it changes. |
| `docs/08-limitations.md` | Which numbers are measurements and which are assumptions. |
| `docs/09-automated-refresh.md` | The scheduled satellite-data refresh and its setup. |

---

## `GEE/`

A pointer only. It used to hold a second, diverged copy of the Earth Engine
script; see `GEE/README.md` for why it was removed.

---

## Generated files, in one list

Do not hand-edit these. Regenerate them, then commit the result:

```
Machine Learning & Prediction/Results/*        (all of it)
frontend/data/grid.geojson                    (the dashboard's only data file)
Decision-Support/recommendation.csv
Decision-Support/excluded.csv
Decision-Support/ranking.csv
```

To regenerate everything:

```bash
cd "Machine Learning & Prediction"
python scripts/preprocess.py
python scripts/train_regression.py
python scripts/tier_and_recommend.py
python scripts/export_grid_geojson.py
cd ../Decision-Support
python member3_decision_support.py
```

CI runs exactly this and fails if the result differs from what is committed.
