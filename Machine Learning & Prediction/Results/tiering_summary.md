# Tiering and recommendation summary

> Heat_Risk is biased high by the uncorrected NDVI (Remote Sensing SPEC_AUDIT #3). Tiers are indicative ranks, not calibrated risk levels. Costs are planning placeholders.

## Thresholds actually applied

| Rule | Value |
|---|---|
| Heat_Risk q0.25 (Low boundary) | 0.005661 |
| Heat_Risk q0.75 (High boundary) | 0.241290 |
| NDVI vegetation split (q0.50) | 0.179546 |

## Outcome

| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) |
|---|---|---|---|---|---|
| High | Cool roof | 81 | 29.47 | 0.210 | 43,339,471 |
| High | Tree cover | 1,955 | 28.70 | 0.115 | 653,637,330 |
| Low | None | 2,036 | 24.92 | 0.243 | 0 |
| Medium | Green park | 4,072 | 27.17 | 0.181 | 907,649,819 |

**Total notional programme cost: INR 1,604,626,620** (placeholder unit rates - see README section 5).
