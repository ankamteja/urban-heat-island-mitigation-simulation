# Urban Heat Island Dashboard — Frontend

Interactive dashboard for Guwahati: a continuous thermal surface over the 100 m
grid, an on-demand prediction of post-mitigation temperature, ecology pointers
marking where each cooling measure is viable, and an analytics panel.

## Running locally

```
cd "Urban Heat Island Mitigation"
py -m http.server 8000
```

Open `http://localhost:8000/frontend/`. It must be served over HTTP — the
dashboard fetches a GeoJSON file, which `file://` blocks.

## How it works

### The heat field is interpolated, not drawn as polygons

`js/heatField.js` is a custom Leaflet layer. Rather than stroking 8,144 squares,
it reconstructs a continuous temperature field:

1. Each cell splats bilinearly into two float accumulators — one for weight,
   one for weight × normalised temperature.
2. A **separable box blur** (3 passes ≈ Gaussian) diffuses both buffers. Because
   it uses a running sum, cost is O(1) in the blur radius, so the radius can be
   large enough to close the gaps in a sparse grid without a performance penalty.
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

## Data contract

The dashboard reads `data/grid.geojson`, falling back to `mock_data/grid.geojson`.
Each feature needs:

| Field                | Type   | Example             | Notes                                     |
|----------------------|--------|---------------------|-------------------------------------------|
| `grid_id`            | string | `"+102027+29089"`   | Unique per cell                           |
| `temperature`        | number | `27.7`              | °C. Cells without one are skipped         |
| `ndvi`               | number | `0.246`             | −1 to 1; `null` renders as N/A            |
| `priority`           | string | `"High"`            | Drives the filter                         |
| `recommended_action` | string | `"Tree cover"`      | See `INTERVENTIONS` in `js/config.js`     |
| `cost_estimate`      | number | `222944`            | ₹ INR                                     |

Geometry must be a polygon per cell. `"nan"` and missing actions normalise to
`"None"`.

To swap in new pipeline output, replace `data/grid.geojson` keeping these field
names. No code changes needed.

## Cooling model

`INTERVENTIONS` in `js/config.js` maps each measure to an expected temperature
drop. These are **planning-grade indicative values**, not field measurements —
they set relative priority and are not a performance guarantee.

| Measure          | Modelled drop |
|------------------|---------------|
| High-albedo roof | 2.9 °C        |
| Urban tree canopy| 2.4 °C        |
| Retention pond   | 2.2 °C        |
| Green park       | 1.8 °C        |
| Vegetated roof   | 1.5 °C        |

## Features

- Continuous blended thermal surface over a dark basemap
- Prediction pane revealed only after an area is selected
- Ecology pointers per measure, with cooling, cost and NDVI in the popup
- Analytics: distribution shift, priority mix, NDVI vs. temperature, cooling vs. cost
- Priority filter, location search, click any point for cell detail
- Keyboard-accessible controls, `prefers-reduced-motion` respected

## File structure

```
frontend/
  index.html
  style.css
  data/grid.geojson        real pipeline output (8,144 cells)
  mock_data/grid.geojson   fallback
  js/
    config.js       colour ramp, intervention model, ecology catalogue
    dataLoader.js   fetch, normalise, summarise
    heatField.js    the blended-surface Leaflet layer
    mapView.js      basemap, legend, map sync
    selection.js    drag-box area selection
    ecology.js      intervention site derivation + markers
    analytics.js    KPIs and Chart.js views
    compareView.js  two-pane orchestration
    popup.js        cell popup markup
    filters.js      priority filter
    main.js         bootstrap
```

## Known limitations

- NDVI is uncorrected upstream, so the vegetation–temperature relationship is
  attenuated (see the Machine Learning module's `SPEC_AUDIT.md`).
- Cooling values and costs are planning assumptions, not measured or tendered.
- One Landsat pass — no seasonal or diurnal variation.
