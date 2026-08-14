# Urban Heat Island Mitigation Simulation — Guwahati

Analysis of the Urban Heat Island effect in Guwahati, Assam using Landsat 8 remote sensing, Google Earth Engine, and grid-based spatial analysis. The city is divided into ~8,100 hundred-metre cells; each cell gets a land surface temperature, a vegetation index, a priority tier, a recommended mitigation action and a costed estimate, and the result is explorable in a browser dashboard.

**New here? Start with [`docs/`](./docs/README.md)** — it covers architecture, a clean-clone build, and a walkthrough of every script.

---

## Quick start

Serve the repository root over HTTP (the dashboard fetches GeoJSON, which `file://` blocks):

```bash
python3 -m http.server 8000
```

| | |
|---|---|
| Landing page | `http://localhost:8000/` |
| Dashboard | `http://localhost:8000/frontend/` |
| Slide deck | `http://localhost:8000/presentation/deck.html` |
| Architecture diagram | `http://localhost:8000/presentation/architecture.html` |

## Modules

| Module | What it owns | Docs |
|---|---|---|
| **[Remote Sensing & Data Engineering](./Remote%20Sensing%20%26%20Data%20Engineering/)** | Study-area boundary, Google Earth Engine workflow producing LST / NDVI / NDBI / land cover, the 100 m grid, and the exported grid dataset every other module consumes. | [README](./Remote%20Sensing%20%26%20Data%20Engineering/README.md) · [spec audit](./Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md) · [guide](./docs/03-remote-sensing.md) |
| **[Machine Learning & Prediction](./Machine%20Learning%20%26%20Prediction/)** | LST regression, quantile-based priority tiering, the rule-based action/cost/cooling engine, and the `grid.geojson` the dashboard renders. | [README](./Machine%20Learning%20%26%20Prediction/README.md) · [spec audit](./Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md) · [guide](./docs/04-machine-learning.md) |
| **[Decision-Support](./Decision-Support/)** | An independent cooling-per-rupee recommender with hard suitability rules and a budget-constrained greedy ranking. | [README](./Decision-Support/README.md) · [guide](./docs/05-decision-support.md) |
| **[frontend](./frontend/)** | Leaflet dashboard rendering the grid as a continuous blended thermal surface, with a selection-gated prediction of post-mitigation temperature, ecology pointers and analytics. | [README](./frontend/README.md) · [guide](./docs/06-frontend.md) |
| **[presentation](./presentation/)** | A 15-slide deck and a standalone system architecture diagram, both static HTML. | [README](./presentation/README.md) |

## Data flow

```
Remote Sensing (Google Earth Engine)
        │  Guwahati_Urban_Heat_Dataset.csv
        ├──────────────────────────────┐
        ▼                              ▼
Machine Learning & Prediction    Decision-Support
        │  grid.geojson                │  recommendation.csv / ranking.csv
        ▼                              ▼
    frontend dashboard          budget-ordered intervention list
```

Full detail, including every column of every file crossing a module boundary, is in [`docs/07-data-contracts.md`](./docs/07-data-contracts.md).

## Headline numbers

| | |
|---|---|
| Grid cells | 8,144 at 100 m |
| Surface temperature | 20.9 – 33.1 °C (mean 27.0 °C) |
| Canonical model | RandomForest, R² 0.901, RMSE 0.52 °C (random split) |
| Actionable cells | 6,108 |
| Modelled mean drop | −1.20 °C |
| Notional programme cost | ₹160.5 Cr (placeholder unit rates) |

Cooling values come from the pipeline's own `cooling_c` field and are planning
assumptions, not measurements — see the honesty notes below.

## Honesty notes

This project documents its own weaknesses rather than hiding them. Before quoting any number from it:

- [`INTEGRATION_AUDIT.md`](./INTEGRATION_AUDIT.md) — cross-module audit: what is wired to what, and where two modules disagree.
- [`docs/08-limitations.md`](./docs/08-limitations.md) — consolidated list of which figures are measurements and which are planning assumptions.
- [`IMPROVEMENTS.md`](./IMPROVEMENTS.md) — prioritized list of what's still worth doing, and a record of what was already fixed.

The headline caveat: **the NDVI in the committed dataset is uncorrected** and therefore compressed low, which biases `Heat_Risk` and everything derived from it. The fix is committed in the Earth Engine script; regenerating the data requires a run in an Earth Engine account. See [`docs/08-limitations.md`](./docs/08-limitations.md).

Model performance also falls sharply under spatial block cross-validation
(R² 0.901 → ~0.15): the model interpolates well inside the studied area but does
not yet transfer to an unseen district.

## Deployment

The web layer is fully static. [`vercel.json`](./vercel.json) and
[`.vercelignore`](./.vercelignore) configure a Vercel deployment that ships only
`frontend/` and `presentation/` (~7 MB); no build step is required.

## Licence

[MIT](./LICENSE) for the code. Third-party data (geoBoundaries, Landsat, ESA WorldCover, OpenStreetMap) carries its own terms — see the attribution section of the licence file.
