# Urban Heat Island Mitigation Simulation — Guwahati

Analysis of the Urban Heat Island effect in Guwahati, Assam using Landsat 8 remote sensing, Google Earth Engine, and grid-based spatial analysis.

## Modules

- **[Remote Sensing & Data Engineering](./Remote%20Sensing%20%26%20Data%20Engineering/)** — satellite data acquisition and preparation: study-area boundary, LST and NDVI generation in Google Earth Engine, 100 m grid construction, and per-grid feature extraction.
  - [Module README](./Remote%20Sensing%20%26%20Data%20Engineering/README.md)
  - [Spec compliance audit](./Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md)
- **[Machine Learning & Prediction](./Machine%20Learning%20%26%20Prediction/)** — turns the grid dataset into mitigation guidance: LST regression, quantile-based priority tiering, a rule-based action/cost engine, and a `grid.geojson` export for the dashboard.
  - [Module README](./Machine%20Learning%20%26%20Prediction/README.md) — **read the NDVI caveat first**
  - [Spec compliance audit](./Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md)
- **[Decision Support](./Decision-Support/)** — rule-based suitability filtering, intervention assignment, and ranking by cooling benefit per rupee.
  - [Module README](./Decision-Support/README.md)
- **[Frontend dashboard](./frontend/)** — the 100 m grid rendered as a continuous blended thermal surface, with a selection-gated prediction of post-mitigation temperature, ecology pointers, and analytics.
  - [Module README](./frontend/README.md)
- **[Presentation](./presentation/)** — a 15-slide deck and a standalone system architecture diagram.
  - [Module README](./presentation/README.md)

## Quick start

```
py -m http.server 8000
```

- Dashboard — `http://localhost:8000/frontend/`
- Deck — `http://localhost:8000/presentation/deck.html`
- Architecture diagram — `http://localhost:8000/presentation/architecture.html`

## Headline numbers

| | |
|---|---|
| Grid cells | 8,144 at 100 m |
| Surface temperature | 20.9 – 33.1 °C (mean 27.0 °C) |
| Canonical model | RandomForest, R² 0.901, RMSE 0.52 °C (random split) |
| Actionable cells | 6,108 |
| Modelled mean drop | −1.51 °C |
| Notional programme cost | ₹160.5 Cr (placeholder unit rates) |

Model performance falls sharply under spatial block cross-validation, and NDVI is
uncorrected upstream — both are documented in the module spec audits and stated
in the deck.
