# Documentation

Everything needed to understand, build, run and modify this project.

## Reading order

**New to the project — read these three, in order:**

1. **[Architecture](./01-architecture.md)** — the four modules, what each owns, how data actually flows between them, and where the seams are.
2. **[Setup and build](./02-setup-and-build.md)** — clean clone to a running dashboard. Exact commands, in dependency order.
3. **[Limitations](./08-limitations.md)** — which numbers in this repo are measurements and which are assumptions. Read before quoting anything.

**Working on one module — go straight to its guide:**

| Guide | Covers |
|---|---|
| [03 — Remote Sensing](./03-remote-sensing.md) | `urban_heat_analysis.js` section by section: the Landsat collection, scale/offset arithmetic, cloud masking, grid construction, the exports. How to run it in Earth Engine. |
| [04 — Machine Learning](./04-machine-learning.md) | The four Python scripts in order, every named constant and why it holds that value, what the reported R² does and does not mean. |
| [05 — Decision-Support](./05-decision-support.md) | The intervention catalogue, the proxy land-cover classifier, the cooling-per-rupee greedy ranking, the budget cut. |
| [06 — Frontend](./06-frontend.md) | Script load order, Leaflet layer mechanics, the compare-view transform, how to point the dashboard elsewhere. |

**Changing something that crosses a module boundary — start here:**

- **[07 — Data contracts](./07-data-contracts.md)** — every file that passes between modules, column by column, with types, units and real ranges.

## Audits

These are separate from the guides. The guides describe how the project works; the audits describe how well.

| Document | Question it answers |
|---|---|
| [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md) | Does the project work as one system? What is wired to what, and where do two modules disagree? |
| [`Remote Sensing & Data Engineering/SPEC_AUDIT.md`](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md) | Does the satellite-data module meet its spec, item by item? |
| [`Machine Learning & Prediction/SPEC_AUDIT.md`](../Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md) | Same, for the modelling module. |

## The shortest possible orientation

Guwahati is divided into 8,144 cells of roughly 100 m. Google Earth Engine measures each cell's temperature and vegetation. A Python rule engine ranks each cell by heat risk and assigns it a costed mitigation action. A Leaflet page draws the result twice — as it is, and as it would be after every recommendation was carried out.

The largest known problem: the vegetation index in the committed data was computed without a required rescale, so it is systematically too low, and everything derived from it is biased. The fix is in the source; the data has not been regenerated because that needs a Google Earth Engine account. [Details](./08-limitations.md).
