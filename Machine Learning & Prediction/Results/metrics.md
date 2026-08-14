# Regression metrics

Target: **LST** (degrees C). Seed: `42`. Rows: 8,144. Test fraction: 20%.

> NDVI comes from the corrected surface-reflectance export.

> Quote the **spatial_block** R2, not the random_80_20 one. Adjacent 100 m cells are near-duplicates, so a random split leaks most test answers through their neighbours and flatters the model badly.

| Split | Features | Model | RMSE (C) | MAE (C) | R2 |
|---|---|---|---|---|---|
| random_80_20 | base | LinearRegression | 1.0515 | 0.8083 | 0.5954 |
| random_80_20 | base | RandomForest | 0.5354 | 0.4104 | 0.8951 |
| random_80_20 | base+spatial_lag | LinearRegression | 0.3972 | 0.3023 | 0.9423 |
| random_80_20 | base+spatial_lag | RandomForest | 0.3725 | 0.2794 | 0.9492 |
| spatial_block | base | LinearRegression | 0.9342 | 0.7408 | 0.3594 |
| spatial_block | base | RandomForest | 0.8146 | 0.6411 | 0.5130 |
| spatial_block | base+spatial_lag | LinearRegression | 1.0769 | 0.8313 | 0.1489 |
| spatial_block | base+spatial_lag | RandomForest | 1.1032 | 0.8520 | 0.1068 |

## Feature importances (canonical model)

| Feature | Importance |
|---|---|
| NDBI | 0.4081 |
| Latitude | 0.2635 |
| Longitude | 0.2202 |
| NDVI | 0.0742 |
| Vegetation | 0.0340 |
