# Urban Heat Island Mitigation Simulation — Guwahati

Analysis of the Urban Heat Island effect in Guwahati, Assam using Landsat 8 remote sensing, Google Earth Engine, and grid-based spatial analysis.

## Modules

- **[Remote Sensing & Data Engineering](./Remote%20Sensing%20%26%20Data%20Engineering/)** — satellite data acquisition and preparation: study-area boundary, LST and NDVI generation in Google Earth Engine, 100 m grid construction, and per-grid feature extraction.
  - [Module README](./Remote%20Sensing%20%26%20Data%20Engineering/README.md)
  - [Spec compliance audit](./Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md)
- **[Machine Learning & Prediction](./Machine%20Learning%20%26%20Prediction/)** — turns the grid dataset into mitigation guidance: LST regression, quantile-based priority tiering, a rule-based action/cost engine, and a `grid.geojson` export for the dashboard.
  - [Module README](./Machine%20Learning%20%26%20Prediction/README.md) — **read the NDVI caveat first**
  - [Spec compliance audit](./Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md)
