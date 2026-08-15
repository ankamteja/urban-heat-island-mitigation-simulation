# 2. Setup and build

Clean clone to a running dashboard. Every command here has been executed as written.

**Contents**

- [What you need](#what-you-need)
- [The short version](#the-short-version)
- [Step 1 — clone](#step-1--clone)
- [Step 2 — Python environment](#step-2--python-environment)
- [Step 3 — run the ML pipeline](#step-3--run-the-ml-pipeline)
- [Step 4 — run Decision-Support](#step-4--run-decision-support)
- [Step 5 — serve the dashboard](#step-5--serve-the-dashboard)
- [The part that needs Google Earth Engine](#the-part-that-needs-google-earth-engine)
- [Troubleshooting](#troubleshooting)

---

## What you need

| For | Requirement |
|---|---|
| Everything except the satellite step | Python 3.12 or newer, and a browser |
| Regenerating the satellite data | A Google Earth Engine account — see [below](#the-part-that-needs-google-earth-engine) |
| Viewing the dashboard | Any modern browser; an internet connection, because map tiles and the Leaflet library load from CDNs |

**You do not need Earth Engine to run this project.** The satellite export is already committed. Earth Engine is only required if you want to *regenerate* it — which is currently the one outstanding piece of work. Everything else runs offline apart from the dashboard's map tiles.

There is nothing to install for the frontend. No `npm`, no bundler, no build step.

## The short version

If you just want it running:

```bash
git clone https://github.com/ankamteja/urban-heat-island-mitigation-simulation.git
cd urban-heat-island-mitigation-simulation

python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r "Machine Learning & Prediction/requirements.txt"

cd frontend && python3 -m http.server 8000
```

Open <http://localhost:8000/>. The dashboard renders from data already in the repo — you do not have to run the pipeline first.

The rest of this page is for when you want to regenerate that data yourself.

---

## Step 1 — clone

```bash
git clone https://github.com/ankamteja/urban-heat-island-mitigation-simulation.git
cd urban-heat-island-mitigation-simulation
```

The repository is about 25 MB. Several committed CSVs are multi-megabyte because they carry a GeoJSON polygon per row — this is intentional, so that every stage's output is inspectable without re-running anything.

One file is deliberately **not** committed: `Machine Learning & Prediction/Models/heat_risk_model.pkl`. The random forest is trained with unbounded depth, so the pickle is around 170 MB — over GitHub's 100 MB per-file limit. It is fully reproducible from a fixed random seed by running `train_regression.py`. See `.gitignore`.

## Step 2 — Python environment

A virtual environment is a private copy of Python and its packages, scoped to this project, so installing here cannot disturb anything else on your machine.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r "Machine Learning & Prediction/requirements.txt"
```

Quote the path — the directory name contains spaces and an ampersand, and an unquoted `&` will background your shell command.

`requirements.txt` pins the versions verified for the module:

```
pandas==3.0.5   numpy==2.4.6   scipy==1.18.0   scikit-learn==1.9.0
shapely==2.1.2  matplotlib==3.11.0  joblib==1.5.3
```

Notably absent: `geopandas`, `fiona`, `pyproj`. The geometry in this project is plain GeoJSON text, so `shapely` plus the standard-library `json` module covers every geometric operation without pulling in the GDAL toolchain — which is the single most painful dependency in the Python geospatial world. Keep it that way.

Decision-Support has no separate requirements file. It needs `pandas`, `numpy` and `shapely`, all of which the file above already installs.

**Verify:**

```bash
python -c "import pandas, numpy, shapely, sklearn, matplotlib; print('ok')"
```

## Step 3 — run the ML pipeline

Four scripts, strictly in this order — each reads the previous one's output.

```bash
cd "Machine Learning & Prediction"
python scripts/preprocess.py
python scripts/train_regression.py
python scripts/tier_and_recommend.py
python scripts/export_grid_geojson.py
```

| Script | Reads | Writes | Roughly |
|---|---|---|---|
| `preprocess.py` | `../Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv` | `Results/preprocessed.csv` (2.9 MB) | seconds |
| `train_regression.py` | `Results/preprocessed.csv` | `Results/metrics.json`, `metrics.md`, `pred_vs_actual.png`, `feature_importances.png`, and `Models/heat_risk_model.pkl` (~170 MB, gitignored) | a minute or two |
| `tier_and_recommend.py` | `Results/preprocessed.csv` | `Results/tiered.csv` (3.3 MB), `tiering_summary.md`, `priority_map.png` | seconds |
| `export_grid_geojson.py` | `Results/tiered.csv` | `frontend/data/grid.geojson` (3.6 MB, 8,144 features) | seconds |

Each script resolves its own paths from `__file__`, so they run correctly from any working directory. `cd` into the module only for convenience.

**What good output looks like.** `tier_and_recommend.py` ends with:

```
Total notional programme cost: INR 1,604,626,620
```

and `export_grid_geojson.py` ends with:

```
Built and validated 8,144 features
temperature range: 20.9 to 33.1 C
cooling range: 0.0 to 2.0 C (assumed)
```

If the feature count is not 8,144, or `validate()` raises, something upstream changed — do not proceed to the dashboard with a file that failed validation.

**Then copy the result to the dashboard.** This is a manual step on purpose:

```bash
```

Regenerating `grid.geojson` does **not** update what the dashboard shows until you copy it across. The alternative — having the browser fetch across `../Machine Learning & Prediction/Results/` — means URL-encoding a path containing a space and an ampersand, which is fragile. The copy is the deliberate trade.

## Step 4 — run Decision-Support

Independent of the ML module; it reads the same source CSV directly.

```bash
python Decision-Support/member3_decision_support.py
```

Writes three files into `Decision-Support/`:

| File | Rows | Contents |
|---|---|---|
| `recommendation.csv` | 6,108 | one row per cell that has a valid intervention |
| `ranking.csv` | 6,108 | the same cells sorted by cooling-per-rupee, with a cumulative cost and a `within_budget` flag |
| `excluded.csv` | 2,036 | cells with no valid intervention, and why |

Expected tail:

```
Budget INR 5,000,000: funds top 1000 of 6108 recommended cells
```

This regenerates the committed files byte-for-byte. If your output differs, your library versions differ from the pinned ones.

## Step 5 — serve the dashboard

```bash
cd frontend
python3 -m http.server 8000
```

Open <http://localhost:8000/>.

**You must serve over HTTP.** Double-clicking `index.html` gives you a `file://` URL, and the dashboard will show "Failed to load map data." The reason: it fetches its data with the browser's `fetch()` API, which browsers refuse to use on `file://` URLs as a security measure — a local page could otherwise read arbitrary files off your disk. Any static server works; `http.server` ships with Python.

**What you should see:** two maps side by side, "Current" and "After Intervention", roughly 8,000 coloured squares over Guwahati, four filter buttons across the top, a four-band legend bottom-right, and a search box on the left map. Clicking a cell opens a popup with its temperature, NDVI, priority, recommended action and cost.

The dashboard needs `frontend/data/grid.geojson`, which step 4 writes directly. There is no synthetic fallback: a mock grid used to exist, but a failed fetch silently rendering invented numbers as measurements was judged worse than an error message.

---

## The part that needs Google Earth Engine

`Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js` does not run on your machine. Earth Engine is a hosted service: you write JavaScript in a browser IDE, Google runs it on their satellite archive, and results are written to your Google Drive.

You need this only to regenerate `Guwahati_Urban_Heat_Dataset.csv` — and right now, **somebody should**, because the committed copy predates a correctness fix. See [08-limitations.md](./08-limitations.md).

Outline:

1. Sign up at <https://earthengine.google.com/> (free for research and education; approval is not instant).
2. Upload `Remote Sensing & Data Engineering/Boundary/guwahati_boundary.geojson` as an Earth Engine asset.
3. Open <https://code.earthengine.google.com/>, paste in the script, and **edit the asset path near the top** — it currently points at `projects/urban-heat-guwahati/assets/guwahati_boundary`, which is private to the original author. Substitute your own.
4. Run. Open the **Tasks** tab and start each export individually — Earth Engine queues them rather than running them automatically.
5. Download the results from Google Drive and place them in `Remote Sensing & Data Engineering/Dataset/` and `Results/`.
6. Re-run steps 3 and 4 above, since every downstream number derives from that CSV.

Full walkthrough: [03-remote-sensing.md](./03-remote-sensing.md).

---

## Troubleshooting

**`bash: Engineering/requirements.txt: No such file or directory`, or your terminal returns immediately**
You did not quote a path containing `&`. The shell read the ampersand as "run in background". Always quote paths in this repo.

**`FileNotFoundError: ... Guwahati_Urban_Heat_Dataset.csv`**
You are not in a complete clone, or the file was moved. Every script resolves this path relative to its own location, so your working directory is not the cause.

**`ModuleNotFoundError: No module named 'shapely'`**
The virtual environment is not active. Re-run the `source .venv/bin/activate` line — activation does not persist across terminal sessions.

**Dashboard shows "Failed to load map data"**
Either you opened it as a `file://` URL, or `frontend/data/grid.geojson` is missing. Confirm with `curl -I http://localhost:8000/data/grid.geojson` — you want `200`.

**The map is blank but no error appears**
Map tiles come from OpenStreetMap over the internet. Without a connection you get the grid squares on a white background, which is correct behaviour, not a bug.

**`validate()` raises `recommended_action ... is not one of [...]`**
The tiering step emitted an action the dashboard does not know. That guard exists because a wrong label there is silent in the browser rather than loud in the pipeline. Fix `ACTION_TABLE` in `tier_and_recommend.py`; do not weaken the check.

**Numbers differ from the committed outputs**
Compare your installed versions against `requirements.txt`. Small floating-point differences (around 1e-16 relative) between library builds are expected and harmless; anything larger is not.

---

Next: [03-remote-sensing.md](./03-remote-sensing.md) for the satellite stage, or [01-architecture.md](./01-architecture.md) if you skipped it.
