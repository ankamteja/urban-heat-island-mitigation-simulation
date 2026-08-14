# Urban Heat Island Dashboard — Frontend

Interactive dashboard for Guwahati: a continuous thermal surface over the 100 m
grid, an on-demand prediction of post-mitigation temperature, ecology pointers
marking where each cooling measure is viable, and an analytics panel.

A deeper walkthrough of every file lives in [`../docs/06-frontend.md`](../docs/06-frontend.md).

## Running locally

Serve the **repository root**, not this directory — the landing page links
across folders:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/frontend/`. You must serve over HTTP. Opening
`index.html` as a `file://` URL fails — the dashboard loads its data with
`fetch()`, which browsers block for local files.

## How it works

### The heat field is interpolated, not drawn as polygons

`js/heatField.js` is a custom Leaflet layer. Rather than stroking 8,144 squares,
it reconstructs a continuous temperature field:

1. Each cell splats bilinearly into two float accumulators — one for weight,
   one for weight × normalised temperature.
2. A **separable box blur** (3 passes ≈ Gaussian) diffuses both buffers. Because
   it uses a running sum, cost is O(1) in the blur radius, so the radius can be
   large enough to close the gaps in a sparse grid without a performance penalty
   (~6 ms per redraw).
3. Dividing the two buffers per pixel recovers temperature — so colour still
   means degrees Celsius, not point density.
4. The low-resolution result is upscaled with bilinear filtering, which removes
   any remaining trace of the square lattice.

Tuning lives in the `FIELD` constant. `blend` (radius as a multiple of cell
spacing) trades smoothness against retained thermal contrast; 5.5 keeps roughly
91% of the contrast of an unblended field while removing all grid artefacts.

### The colour ramp is derived from the data

A fixed 22–33 °C ramp wastes most of its range: the bulk of the city sits in a
narrow 26–28 °C band. `setTempDomain()` anchors the ramp on the 2nd and 98th
percentiles at load time (currently 23–30 °C) and then holds it fixed, so the
current and predicted surfaces stay directly comparable.

### The prediction is gated behind a selection

The right-hand pane stays collapsed until the user drags a box on the current
surface (`js/selection.js`). On selection the dashboard renders the
post-mitigation field for those cells only, drops ecology pointers, and rescopes
the analytics panel to the selection.

### Ecology pointers

`js/ecology.js` refines the model's coarse `recommended_action` into distinct
measures using temperature and vegetation cover — a cool-roof cell with moderate
NDVI becomes a green roof; a hot, bare park cell becomes a retention pond. Sites
are then thinned by a round-robin across measure types with a global minimum
separation, so pointers mark representative projects and never overlap.

## Data

The dashboard reads **`data/grid.geojson`** — the real pipeline output, 8,144
Guwahati cells, produced by
`Machine Learning & Prediction/scripts/export_grid_geojson.py` and copied here.

The copy is deliberate rather than a relative `fetch()` across module
directories — the ML module's path contains a space and an ampersand, which is
fragile to URL-encode from the browser. It also means **regenerating the file
does not update the dashboard until you copy it across.**

There is no synthetic fallback: the dashboard loads
`data/grid.geojson` or shows an error. It is excluded from production deploys via `.vercelignore`, so a
data failure in production surfaces as an error rather than silently rendering
mock values.

## Data contract

Each GeoJSON feature must have these properties. `export_grid_geojson.py`
enforces this exact key set in its `validate()` function and refuses to write
a file that does not match — so if the dashboard renders, the contract held.

| Field                | Type    | Example      | Notes                                              |
|----------------------|---------|--------------|----------------------------------------------------|
| `grid_id`            | string  | `"+102027+29089"` | Unique ID per cell (join key)                 |
| `temperature`        | number  | `27.7`       | °C. Real range 20.9–33.1. Cells without one are skipped |
| `ndvi`               | number  | `0.246`      | Vegetation index. **Uncorrected — see below**      |
| `priority`           | string  | `"High"` / `"Medium"` / `"Low"` | Drives the filter buttons       |
| `recommended_action` | string  | `"Tree cover"` / `"Cool roof"` / `"Green park"` / `"None"` | Selects the measure |
| `cost_estimate`      | number  | `334350`     | ₹ INR, integer                                     |
| `cooling_c`          | number  | `0.8`        | °C this cell's intervention is assumed to remove   |

Every field is handled defensively — a missing or malformed value renders as
"N/A" or grey rather than throwing. `"nan"` and missing actions normalise to
`"None"`.

**Geometry:** one Polygon per feature, a single grid cell. Real cells are
0.00089832° squares in EPSG:4326 — about 89.8 m × 99.3 m at this latitude, not
exactly 100 m × 100 m.

## Cooling model

The predicted surface subtracts each cell's own **`cooling_c`** from its
temperature, wherever `recommended_action` is present and not `"None"`. A
`cooling_c` of `0` is respected as a real zero, not treated as missing.

If a feature carries no `cooling_c` —
`dataLoader.js` falls back to the per-measure table in `INTERVENTIONS`
(`js/config.js`). That table also supplies the label and glyph for each measure,
and covers the two derived measures the pipeline does not emit directly.

Values currently carried by the pipeline:

| Measure    | `cooling_c` | Cells |
|------------|-------------|-------|
| Green park | 2.0 °C      | 4,072 |
| Cool roof  | 1.0 °C      | 81    |
| Tree cover | 0.8 °C      | 1,955 |
| None       | 0.0 °C      | 2,036 |

**These are assumptions, not predictions.** They set relative priority and are
not a performance guarantee.

## Features

- Continuous blended thermal surface over a dark basemap
- Prediction pane revealed only after an area is selected
- Ecology pointers per measure, with cooling, cost and NDVI in the popup
- Analytics: distribution shift, priority mix, NDVI vs. temperature, cooling vs. cost
- Priority filter, location search, click any point for cell detail
- Keyboard-accessible controls, `prefers-reduced-motion` respected

## Known limitations

- `ndvi` values shown in popups are uncorrected and compressed low (max 0.386
  across the whole city, where 0.7–0.85 would be expected). The fix is
  committed in the Earth Engine script but the data has not been regenerated.
  See [`../docs/08-limitations.md`](../docs/08-limitations.md).
- `cost_estimate` figures are order-of-magnitude planning placeholders, not
  procured or tendered costs.
- Coverage is the geoBoundaries ADM3 "Guwahati" polygon (~81 km²), which is
  smaller than the full municipal extent.
- One Landsat pass — no seasonal or diurnal variation.

## File structure

```
frontend/
├── index.html          script load order matters — plain globals, no modules
├── style.css
├── data/
│   └── grid.geojson    real pipeline output, 8,144 cells
│   ├── generate_mock.py
│   └── grid.geojson    900 synthetic cells, offline development only
└── js/
    ├── config.js       colour ramp, intervention model, ecology catalogue
    ├── dataLoader.js   fetch, normalise, summarise
    ├── heatField.js    the blended-surface Leaflet layer
    ├── mapView.js      basemap, legend, map sync
    ├── selection.js    drag-box area selection
    ├── ecology.js      intervention site derivation + markers
    ├── analytics.js    KPIs and Chart.js views
    ├── compareView.js  two-pane orchestration
    ├── popup.js        per-cell popup markup
    ├── filters.js      priority filter buttons
    └── main.js         entry point
```
