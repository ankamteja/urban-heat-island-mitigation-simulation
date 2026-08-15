# 11 — Roadmap to a 9/10 repository

This is the short, ordered improvement plan for turning the project from a
strong decision-support prototype into an outstanding, evidence-backed product.
It is intentionally separate from [`STATUS.md`](../STATUS.md): `STATUS.md`
records what is true now; this page records what should happen next.

## Starting point

The current project is approximately **7.8/10 overall**:

| Area | Current | Why it is not a 9 yet |
|---|---:|---|
| Engineering and reproducibility | 9.0 | Tests and regeneration checks are excellent; linting and frontend modularity are still light. |
| Data engineering | 8.5 | Strong contracts and real inputs, but the analysis is mostly one temporal snapshot. |
| Documentation and licensing | 9.0 | The repository is unusually candid and well mapped. |
| Frontend and deployment | 8.5 | Live and cache-safe, but the payload is large and mobile/accessibility coverage is incomplete. |
| ML and statistics | 5.5 | The model is measured honestly, but it does not drive the visible recommendation. |
| Cooling and cost validity | 4.5 | Cooling is still assumed; only tree-cover direction has a non-causal observational check. |
| Planning readiness | 4.0 | The shortlist is not ready to support procurement or a municipal commitment. |

The target is not to make every score perfect. A 9/10 is earned by removing the
large scientific and product risks while preserving the project's current
honesty.

## Priority plan

### P0 — Make the recommendation uncertainty-aware

**Goal:** stop one uncertain number from determining the entire ₹10 crore
shortlist.

Add low/base/high ranges for every unit rate and cooling value. Run the ranking
for a documented scenario grid or Monte Carlo sample, then expose:

- the probability that each action leads on cooling per rupee;
- the probability that each cell remains funded;
- the cells whose rank is stable versus rate-sensitive;
- a conservative shortlist using lower-bound benefits and upper-bound costs.

Acceptance criteria:

- `shared/constants.json` contains provenance, date, central estimate and range
  for every rate and cooling value;
- `Decision-Support/ranking.csv` includes scenario or stability fields;
- CI checks that the scenario runner is deterministic under a fixed seed;
- the dashboard labels the shortlist as stable or sensitive rather than showing
  one false-precision ordering;
- documentation explains that the current cool-roof-only result is a model
  outcome, not a settled policy decision.

**Expected impact:** the largest improvement to scientific and planning quality.

### P0 — Replace placeholders with an intervention validation design

**Goal:** turn the “after” surface from an asserted scenario into an estimate
with defensible uncertainty.

Use repeated satellite observations and matched controls, or a small field
study, for each intervention class. The minimum useful design is:

1. select treated and comparable untreated cells before deployment;
2. collect multiple pre-period and post-period observations across seasons;
3. control for weather, time of day, land cover, baseline LST and urban form;
4. estimate effect size with uncertainty, not a single flat degree value;
5. keep a held-out geography or time period for validation.

Acceptance criteria:

- a dated data protocol and inclusion/exclusion rules are committed;
- the estimator has a reproducible script and a test fixture;
- cool roof, tree cover and park effects are reported separately;
- the UI distinguishes measured effects, estimated effects and assumptions;
- no intervention value is called “predicted” until it passes the validation
  threshold defined in the protocol.

The current tree-cover check in
[`10 — Tree-cover temperature check`](./10-tree-cover-check.md) is a useful
baseline, but it must not be promoted to causal evidence.

### P1 — Add time and spatial generalisation

**Goal:** make the result useful beyond one daytime scene in one boundary.

- Add seasonal or multi-date Landsat composites and show the observation date.
- Report uncertainty and valid-pixel coverage per cell.
- Evaluate spatial-block, temporal-block and cross-area performance separately.
- Add a second nearby city or held-out district if the project claims transfer.
- Make the date/window/sensor visible in the dashboard and exported manifest.

Acceptance criteria: every headline metric names its spatial and temporal
scope; a refresh cannot silently replace the observation window; and the model
README quotes the same metrics that CI reads from `metrics.json`.

### P1 — Make the model useful or make its boundary explicit

The current RandomForest is evaluated honestly, but downstream decisions come
from rules. Choose one of two defensible directions:

- **Product direction:** remove the implication that ML drives the plan and
  present the model as exploratory diagnostics only; or
- **Research direction:** use out-of-fold predictions or calibrated uncertainty
  in a recommendation component, then prove that it improves held-out spatial
  performance and does not violate land-cover safety rules.

Do not keep a decorative model in the headline story without explaining this
boundary.

### P1 — Reduce the frontend payload and improve accessibility

The browser currently downloads a multi-megabyte polygon GeoJSON while rendering
cell centroids. Add a compact centroid/bounds artifact or vector tiles while
retaining the full polygon source for analysis.

Add:

- keyboard-accessible selection and map summaries;
- a responsive single-map mode for small screens;
- a table/list alternative to map-only information;
- visible land-cover, exclusion reason, source date and data-release ID in the
  cell details;
- automated browser smoke tests for loading, selection and failed-data states.

Acceptance criteria: a mobile viewport is usable without horizontal scrolling,
all actionable information is available without pointer-only interaction, and
the production payload has a measured size budget.

### P2 — Make operations boring and observable

- Configure the Earth Engine secret and run a dry-run refresh in CI.
- Add a deployment smoke test that checks the live release manifest against the
  commit's expected release ID.
- Publish the last successful data refresh and observation date in the UI.
- Add a failure notification for refresh, reproducibility and deployment jobs.
- Pin or lock every runtime dependency and add Python linting/formatting (for
  example Ruff) plus JavaScript linting.
- Add dependency and secret scanning to GitHub Actions.

The repository already has the right safety shape—refresh, regenerate, test,
then commit. This work makes failures visible to the maintainer instead of
requiring manual inspection.

### P2 — Clean the remaining maintainability edges

- Relink and commit the QGIS project with portable relative paths, or document
  it as an intentionally non-portable source artifact.
- Decide whether the two stale `SPEC_AUDIT.md` files should be folded into the
  canonical docs or removed.
- Consider renaming directories containing spaces and `&` only if the team is
  willing to absorb the migration; this is lower value than validation work.
- Add a small schema/version file for every generated artifact, not only the
  frontend grid.

## Definition of “9/10”

The repository is ready for a 9/10 review when all of the following are true:

- the funded shortlist remains understandable under documented cost/cooling
  uncertainty;
- at least one intervention has a repeated-observation or field validation
  estimate, and the others are explicitly marked unvalidated;
- results cover more than one date or clearly state why a snapshot is sufficient
  for the stated use;
- the model’s role is either materially useful or honestly diagnostic;
- the dashboard is fast and usable on mobile and with keyboard assistance;
- a clean clone, scheduled refresh, generated artifacts and live deployment are
  all verified automatically;
- license, data attribution, source dates, release IDs and limitations are
  visible wherever a user could mistake a scenario for a measurement.

## Recommended sequence

1. Add uncertainty ranges and sensitivity ranking.
2. Establish the repeated-observation/field validation protocol.
3. Add temporal coverage and revise the headline metrics.
4. Decide and document the ML boundary.
5. Ship compact frontend data plus mobile/accessibility support.
6. Add deployment smoke tests, notifications, linting and dependency scanning.

This order follows expected decision value, not visual novelty. A prettier map
cannot compensate for a shortlist controlled by unvalidated assumptions.
