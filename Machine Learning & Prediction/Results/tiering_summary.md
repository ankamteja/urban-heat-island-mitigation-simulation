# Tiering and recommendation summary

> Heat_Risk is biased high by the uncorrected NDVI (Remote Sensing SPEC_AUDIT #3). Tiers are indicative ranks, not calibrated risk levels. Costs are planning placeholders.
>
> Expected cooling is a placeholder assumption too, and not even this module's own: the per-action degrees C are copied from the Decision-Support INTERVENTIONS catalogue, which labels them "placeholder engineering estimates for a hackathon demo". They are not measured, fitted or validated for Guwahati - see Rule 5 in scripts/tier_and_recommend.py.

## Thresholds actually applied

| Rule | Value |
|---|---|
| Heat_Risk q0.25 (Low boundary) | 0.005661 |
| Heat_Risk q0.75 (High boundary) | 0.241290 |
| NDVI vegetation split (q0.50) | 0.179546 |

## Outcome

| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) | Mean cooling (C, assumed) |
|---|---|---|---|---|---|---|
| High | Cool roof | 81 | 29.47 | 0.210 | 43,339,471 | 1.00 |
| High | Tree cover | 1,955 | 28.70 | 0.115 | 653,637,330 | 0.80 |
| Low | None | 2,036 | 24.92 | 0.243 | 0 | 0.00 |
| Medium | Green park | 4,072 | 27.17 | 0.181 | 907,649,819 | 2.00 |

**Total notional programme cost: INR 1,604,626,620** (placeholder unit rates - see README section 5).
