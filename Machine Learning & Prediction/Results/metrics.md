# Regression metrics

Target: **LST** (degrees C). Seed: `42`. Rows: 8,144. Test fraction: 20%.

> NDVI is uncorrected (Remote Sensing SPEC_AUDIT #3). Metrics are internally valid but the NDVI-temperature relationship is attenuated.

| Split | Features | Model | RMSE (C) | MAE (C) | R2 |
|---|---|---|---|---|---|
| random_80_20 | base | LinearRegression | 1.4363 | 1.0917 | 0.2475 |
| random_80_20 | base | RandomForest | 0.5209 | 0.3844 | 0.9010 |
| random_80_20 | base+spatial_lag | LinearRegression | 0.4262 | 0.3194 | 0.9337 |
| random_80_20 | base+spatial_lag | RandomForest | 0.4125 | 0.3088 | 0.9379 |
| spatial_block | base | LinearRegression | 1.4810 | 1.3196 | -0.6136 |
| spatial_block | base | RandomForest | 1.0742 | 0.7399 | 0.1510 |
| spatial_block | base+spatial_lag | LinearRegression | 1.2017 | 0.8990 | -0.0624 |
| spatial_block | base+spatial_lag | RandomForest | 1.1801 | 0.8892 | -0.0245 |

## Feature importances (canonical model)

| Feature | Importance |
|---|---|
| Latitude | 0.4885 |
| Longitude | 0.2653 |
| NDVI | 0.2462 |
