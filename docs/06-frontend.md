# 06 — Frontend

The dashboard: `frontend/`. Plain HTML, CSS and JavaScript with no build step,
no bundler and no `package.json`. Serve the folder over HTTP and it runs.

```bash
python3 -m http.server 8000
# dashboard: http://localhost:8000/frontend/
```

`file://` will not work — the page fetches GeoJSON, which the browser blocks on
a file URL. The boot screen says so if the fetch fails.

---

## What it renders

Two synchronised maps. The left shows Guwahati's measured surface temperature.
The right stays hidden until you drag a selection box, then shows the same area
as it would be if every recommendation inside it were carried out.

Below them: a filter row by priority, a KPI strip, and four charts.

---

## The files, in reading order

| File | What it does |
|---|---|
| `js/main.js` | Bootstrap. Loads the grid, then wires every other module together. **Start here.** |
| `js/dataLoader.js` | Fetches the GeoJSON and flattens each feature into the record everything else uses. Also computes the summary statistics behind every KPI and chart. |
| `js/config.js` | The colour ramp, the intervention catalogue, priority colours, currency formatting, and the temperature domain. |
| `js/heatField.js` | The heat surface itself. The most substantial code in the project — see below. |
| `js/mapView.js` | Leaflet setup, basemap tiles, legend, and pane synchronisation. |
| `js/compareView.js` | Orchestrates the two panes, the selection flow and the prediction reveal. |
| `js/selection.js` | Drag-a-box area selection. |
| `js/filters.js` | Priority filter buttons. |
| `js/analytics.js` | KPI cards and the four Chart.js panels. |
| `js/popup.js` | Per-cell popup markup. |
| `js/ecology.js` | Derives illustrative planting sites within a selection and renders their markers. |

All scripts share global scope via `<script>` tags — `view`, `charts` and
`INTERVENTIONS` are globals. It works and the code is disciplined about it, but
nothing prevents a name collision as it grows. ES modules would fix that without
introducing a build step.

---

## Data loading

`main.js` declares one source:

```js
const DATA_SOURCES = ['data/grid.geojson'];
```

There used to be a second entry: a fallback to a hand-written mock grid of 900
synthetic cells spanning a fabricated 28–42 °C. It was removed — if the real
fetch ever failed, the dashboard would quietly render invented numbers as though
they were measurements, which is worse than showing nothing. A failed fetch now
surfaces the error message instead. `data/grid.geojson` is written by the ML module's step 4 — see
[07 — Data contracts](./07-data-contracts.md#contract-4--gridgeojson-the-frontend-contract)
for the exact schema.

`normalize()` in `dataLoader.js` reduces each polygon to a centroid and a
bounding box. **The renderer never uses the full polygon ring** — which means
the 3.7 MB of ring coordinates the browser downloads are averaged down to a
point and discarded. Shipping centroids plus bounds instead would cut the
payload several-fold with no visual change.

It also coerces an action of `'nan'` or `'NaN'` (from a historical pandas
round-trip defect) to `'None'`. The `cooling_c` fallback table in `config.js` is
now unreachable in practice, since the pipeline always emits the field.

---

## The temperature domain

`config.js` holds a colour ramp and a `TEMP_DOMAIN`, but the domain is **not**
hardcoded. `dataLoader.js` calls `setTempDomain()` with the 2nd and 98th
percentiles of whatever it just loaded, and `mapView.js` derives the legend
labels from the same values.

This matters because it removes a whole class of bug. An earlier version
hardcoded buckets at 30/34/38 °C, tuned to the mock data's fabricated 28–42 °C
range; against the real 21–33 °C range that collapsed 98.6% of the city into a
single colour. The legend was a second hardcoded literal that could disagree
with the scale independently.

Now the scale follows the data and the labels follow the scale, so **no retuning
is needed when the pipeline output changes.** Raw min/max is deliberately not
used — a handful of outliers would compress everything else into the middle of
the ramp.

---

## `heatField.js` — how the surface is drawn

Not a heatmap library, and not a density plot. It is Gaussian/Shepard
interpolation, so colour means degrees Celsius rather than "how many points are
near here".

Each cell splats into **two** float accumulators — one for weight, one for
weight × temperature — using bilinear distribution across the four neighbouring
samples so the field does not snap to the accumulator's integer lattice.
Dividing the two per pixel yields an interpolated temperature.

Both accumulators are then blurred with a **separable running-sum box blur**,
three passes to approximate a Gaussian. The running sum makes it O(1) per pixel
regardless of blur radius, which is what allows a radius large enough to close
the gaps in a sparse grid without splatting a kernel per cell.

The result is written to an offscreen canvas at 0.4× resolution and upscaled, so
the browser's own bilinear filter does the final smoothing pass.

Alpha is `1 − exp(−k · weight / reference)`, so sparse edges fade out instead of
ending in a hard rectangle.

Clicking uses `cellAt()`, which buckets cells into a spatial hash at load time
and searches only the 3×3 neighbourhood — O(1) per click rather than a scan of
8,144 cells.

---

## The before/after model

`applyIntervention()` in `dataLoader.js`:

```js
c.cooling > 0 ? { ...c, temp: +(c.temp - c.cooling).toFixed(2) } : c
```

The per-cell `cooling_c` comes from the pipeline. An earlier version subtracted
a flat 3 °C from any cell with an action, regardless of which intervention —
both invented and uniform.

> The cooling values are **assumptions, not predictions.** See
> [08 — Limitations](./08-limitations.md). The "after" map is what the plan
> claims it would achieve, not a forecast.

---

## Dependencies

Loaded from CDNs, all pinned:

| Library | Version | Used for |
|---|---|---|
| Leaflet | 1.9.4 | Maps |
| leaflet-control-geocoder | 2.4.0 | The search box |
| Chart.js | 4.4.1 | The analytics panels |

The geocoder was previously unpinned, meaning an upstream major release could
break the deployed site with no commit to this repository. Adding
subresource-integrity hashes to all three would be the next step.

Basemap tiles come from CARTO's dark theme; OpenStreetMap and CARTO attribution
is required and present.

---

## Deployment

Vercel, from the repository root. `vercel.json` adds a `/dashboard` redirect and
marks `frontend/data/*` as `no-store`. The export script writes a
content-addressed `frontend/data/release.json`; the dashboard reads that
manifest first and requests `grid.geojson` with its SHA-256 checksum in the
query string. A newly deployed dashboard therefore cannot keep using an old
grid response from a browser cache. `.vercelignore` keeps the analysis modules
out of the bundle — only the landing page and `frontend/` ship.

If the public dashboard still reports an old total after this change is merged,
that deployment is not built from this repository revision. Deploy the current
repository root to the Vercel project that owns the public domain.

---

## Known gaps

- **Payload.** 3.7 MB of polygon rings downloaded to render centroids. Vector
  tiles or a centroid-only export would fix it.
- **Mobile.** The dual-map compare view is the centrepiece and is unlikely to
  work on a phone.
- **Accessibility.** The map has no keyboard navigation. ARIA labels exist on
  the legend and panes, but selection is mouse-only.
- **Land cover is not surfaced.** It now decides every recommendation, and
  showing *why* a cell got its action would make the tool far more defensible.
