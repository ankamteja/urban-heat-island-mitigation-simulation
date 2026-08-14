# Urban Heat Island Mitigation Simulation — Guwahati

Analysis of the Urban Heat Island effect in Guwahati, Assam using Landsat 8 remote sensing, Google Earth Engine, and grid-based spatial analysis. The city is divided into ~8,100 hundred-metre cells; each cell gets a land surface temperature, a vegetation index, a priority tier, a recommended mitigation action and a costed estimate, and the result is explorable in a browser dashboard.

**New here? Start with [`docs/`](./docs/README.md)** — it covers architecture, a clean-clone build, and a walkthrough of every script.

---

## Modules

| Module | What it owns | Docs |
|---|---|---|
| **[Remote Sensing & Data Engineering](./Remote%20Sensing%20%26%20Data%20Engineering/)** | Study-area boundary, Google Earth Engine workflow producing LST / NDVI / NDBI / land cover, the 100 m grid, and the exported grid dataset every other module consumes. | [README](./Remote%20Sensing%20%26%20Data%20Engineering/README.md) · [spec audit](./Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md) · [guide](./docs/03-remote-sensing.md) |
| **[Machine Learning & Prediction](./Machine%20Learning%20%26%20Prediction/)** | LST regression, quantile-based priority tiering, the rule-based action/cost/cooling engine, and the `grid.geojson` the dashboard renders. | [README](./Machine%20Learning%20%26%20Prediction/README.md) · [spec audit](./Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md) · [guide](./docs/04-machine-learning.md) |
| **[Decision-Support](./Decision-Support/)** | An independent cooling-per-rupee recommender with hard suitability rules and a budget-constrained greedy ranking. | [README](./Decision-Support/README.md) · [guide](./docs/05-decision-support.md) |
| **[frontend](./frontend/)** | Leaflet split-screen dashboard — current vs. after-intervention, priority filters, per-cell popups. | [README](./frontend/README.md) · [guide](./docs/06-frontend.md) |

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

## Honesty notes

This project documents its own weaknesses rather than hiding them. Before quoting any number from it:

- [`INTEGRATION_AUDIT.md`](./INTEGRATION_AUDIT.md) — cross-module audit: what is wired to what, and where two modules disagree.
- [`docs/08-limitations.md`](./docs/08-limitations.md) — consolidated list of which figures are measurements and which are planning assumptions.

The headline caveat: **the NDVI in the committed dataset is uncorrected** and therefore compressed low, which biases `Heat_Risk` and everything derived from it. The fix is committed in the Earth Engine script; regenerating the data requires a run in an Earth Engine account. See [`docs/08-limitations.md`](./docs/08-limitations.md).

## Licence

[MIT](./LICENSE) for the code. Third-party data (geoBoundaries, Landsat, ESA WorldCover, OpenStreetMap) carries its own terms — see the attribution section of the licence file.
