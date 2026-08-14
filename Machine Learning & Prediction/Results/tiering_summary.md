# Tiering and recommendation summary

> Tiers are relative ranks within Guwahati (Heat_Risk quantiles), not calibrated absolute risk levels. Costs are planning placeholders.
>
> Expected cooling is a placeholder assumption, and not this module's own: the per-action degrees C originate in the Decision-Support catalogue, which labels them "placeholder engineering estimates for a hackathon demo". They are not measured, fitted or validated for Guwahati - see shared/constants.json.
>
> Interventions are gated on real ESA WorldCover land cover: water and wetland cells are never treated, built-up cells receive roof interventions only, and ground interventions are placed only on open land. See shared/uhi_shared.py:assign_action.

## Thresholds actually applied

| Rule | Value |
|---|---|
| Heat_Risk q0.25 (Low boundary) | -0.324837 |
| Heat_Risk q0.75 (High boundary) | 0.039573 |
| NDVI vegetation threshold (absolute) | 0.3 |

## Land cover of the study area

| Land cover | Cells |
|---|---|
| tree_cover | 3,752 |
| built_up | 3,523 |
| cropland | 573 |
| water | 149 |
| grassland | 79 |
| wetland | 44 |
| bare_sparse | 24 |

## Why cells received no action

| Reason | Cells |
|---|---|
| already vegetated (tree cover) - no action needed | 3,752 |
| never-touch land cover (water) | 149 |
| never-touch land cover (wetland) | 44 |
| low priority - no action needed | 42 |

## Outcome

| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) | Mean cooling (C, assumed) |
|---|---|---|---|---|---|---|
| High | Cool roof | 1,770 | 28.64 | 0.281 | 946,829,805 | 1.00 |
| High | Green park | 74 | 28.82 | 0.277 | 75,889,420 | 2.00 |
| High | None | 192 | 26.06 | 0.038 | 0 | 0.00 |
| Low | None | 2,036 | 25.08 | 0.636 | 0 | 0.00 |
| Medium | Cool roof | 1,724 | 27.27 | 0.396 | 922,163,533 | 1.00 |
| Medium | None | 1,759 | 27.11 | 0.497 | 0 | 0.00 |
| Medium | Tree cover | 589 | 27.71 | 0.472 | 196,982,433 | 0.80 |

**Total notional programme cost: INR 2,141,865,191** (placeholder unit rates - see README section 5).
