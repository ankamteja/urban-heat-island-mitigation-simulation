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

Live at **[urban-heat-island-guwahati.vercel.app](https://urban-heat-island-guwahati.vercel.app)**.

## Modules

| Module | What it owns | Docs |
|---|---|---|
| **[Remote Sensing & Data Engineering](./Remote%20Sensing%20%26%20Data%20Engineering/)** | Study-area boundary, Google Earth Engine workflow producing LST / NDVI / NDBI / land cover, the 100 m grid, and the exported grid dataset every other module consumes. | [README](./Remote%20Sensing%20%26%20Data%20Engineering/README.md) · [spec audit](./Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md) · [guide](./docs/03-remote-sensing.md) |
| **[Machine Learning & Prediction](./Machine%20Learning%20%26%20Prediction/)** | LST regression, quantile-based priority tiering, the rule-based action/cost/cooling engine, and the `grid.geojson` the dashboard renders. | [README](./Machine%20Learning%20%26%20Prediction/README.md) · [spec audit](./Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md) · [guide](./docs/04-machine-learning.md) |
| **[Decision-Support](./Decision-Support/)** | An independent cooling-per-rupee recommender with hard suitability rules and a budget-constrained greedy ranking. | [README](./Decision-Support/README.md) · [guide](./docs/05-decision-support.md) |
| **[frontend](./frontend/)** | Leaflet dashboard rendering the grid as a continuous blended thermal surface, with a selection-gated prediction of post-mitigation temperature, ecology pointers and analytics. | [README](./frontend/README.md) · [guide](./docs/06-frontend.md) |

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
| Actionable cells | 4,157 of 8,144 (the rest are water, existing tree cover, or low priority) |
| Modelled drop, treated cells | −0.99 °C |
| Modelled drop, whole grid | −0.51 °C |
| **Recommended programme** | **₹9.99 Cr — 249 cells, all cool roof** |
| Cost if every actionable cell were treated | ₹167.5 Cr (upper bound, not a proposal) |

Read the two cost lines together. ₹167.5 Cr is what treating all 4,157
actionable cells would cost; nothing here recommends that. The recommendation
is the budget-capped set in [`Decision-Support/ranking.csv`](Decision-Support/ranking.csv)
— ₹10 Cr, 249 cells — chosen greedily by cooling per rupee.

Read the two cooling lines together as well. −0.51 °C is averaged over the
whole grid including the 3,987 cells nothing is done to; −0.99 °C is averaged
over the cells actually treated. The larger number is not the more optimistic
one, it is the more narrowly scoped one.

Cooling values come from the pipeline's own `cooling_c` field and are planning
assumptions, not measurements — see the honesty notes below.

## Honesty notes

This project documents its own weaknesses rather than hiding them. Before quoting any number from it:

- [`docs/08-limitations.md`](./docs/08-limitations.md) — which figures are measurements and which are planning assumptions.
- [`STATUS.md`](./STATUS.md) — what works today, what is still open, and how to verify each claim.

The headline caveat: **the cooling figures behind the "after intervention" map
are assumptions, not measurements.** They were never fitted to Guwahati or
validated against a field trial, and they drive both that map and the
cost-effectiveness ranking. Costs are planning placeholders on the same footing.

Model performance also falls under spatial-block cross-validation
(R² 0.895 random split → 0.513 blocked): the model interpolates well inside the
studied area and transfers less well to an unseen district. Quote the blocked
figure.

## Deployment

The web layer is fully static. [`vercel.json`](./vercel.json) and
[`.vercelignore`](./.vercelignore) configure a Vercel deployment that ships only
the landing page and `frontend/` (~2.7 MB); no build step is required.

The Vercel project is not connected to this repository (it is owned by another
account), so pushes do not auto-deploy. Ship changes with `vercel deploy --prod`
from the repository root.

## Licence

[MIT](./LICENSE) for the code. Third-party data (geoBoundaries, Landsat, ESA WorldCover, OpenStreetMap) carries its own terms — see the attribution section of the licence file.
