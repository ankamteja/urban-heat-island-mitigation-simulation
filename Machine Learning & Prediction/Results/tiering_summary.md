# Tiering and recommendation summary

> Tiers are relative ranks within Guwahati (Heat_Risk quantiles), not calibrated absolute risk levels. Costs are planning placeholders.
>
> Expected cooling is a placeholder assumption, and not this module's own: the per-action degrees C originate in the Decision-Support catalogue, which labels them "placeholder engineering estimates for a hackathon demo". They are not measured, fitted or validated for Guwahati - see shared/constants.json.
>
> Interventions are gated on real ESA WorldCover land cover: water and wetland cells are never treated, built-up cells receive roof interventions only, and ground interventions are placed only on open land. See shared/uhi_shared.py:assign_action.

## Thresholds actually applied

| Rule | Value |
|---|---|
| Heat_Risk q0.25 (Low boundary) | -0.246099 |
| Heat_Risk q0.75 (High boundary) | 0.046398 |
| NDVI vegetation threshold (absolute) | 0.3 |

## Land cover of the study area

| Land cover | Cells |
|---|---|
| tree_cover | 3,743 |
| built_up | 3,527 |
| cropland | 576 |
| water | 153 |
| grassland | 80 |
| wetland | 44 |
| bare_sparse | 21 |

## Why cells received no action

| Reason | Cells |
|---|---|
| already vegetated (tree cover) - no action needed | 3,743 |
| never-touch land cover (water) | 153 |
| low priority - no action needed | 108 |
| never-touch land cover (wetland) | 44 |

## Outcome

| Priority | Action | Cells | Mean LST (C) | Mean NDVI | Total cost (INR) | Mean cooling (C, assumed) |
|---|---|---|---|---|---|---|
| High | Cool roof | 1,583 | 28.27 | 0.239 | 635,125,290 | 1.00 |
| High | Green park | 239 | 29.58 | 0.345 | 245,119,737 | 2.00 |
| High | None | 214 | 27.18 | 0.193 | 0 | 0.00 |
| Low | None | 2,036 | 24.92 | 0.542 | 0 | 0.00 |
| Medium | Cool roof | 1,853 | 26.57 | 0.319 | 743,355,856 | 1.00 |
| Medium | None | 1,798 | 26.99 | 0.422 | 0 | 0.00 |
| Medium | Tree cover | 421 | 27.84 | 0.425 | 140,796,827 | 0.80 |

**Total notional programme cost: INR 1,764,397,710** (placeholder unit rates - see README section 5).
