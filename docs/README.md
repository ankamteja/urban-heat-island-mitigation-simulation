# Documentation

Everything needed to understand, build, run and modify this project.

## Status

Four of eight pages are written. The remaining four are tracked in
[`../IMPROVEMENTS.md`](../IMPROVEMENTS.md) as the top priority.

| Page | Status |
|---|---|
| [01 — Architecture](./01-architecture.md) | Written |
| [02 — Setup and build](./02-setup-and-build.md) | Written |
| [03 — Remote Sensing](./03-remote-sensing.md) | Written |
| 04 — Machine Learning | **Not yet written** — see the module's own [README](../Machine%20Learning%20%26%20Prediction/README.md), which is thorough |
| [05 — Decision-Support](./05-decision-support.md) | Written |
| 06 — Frontend | **Not yet written** — see [`frontend/README.md`](../frontend/README.md), which was updated alongside these docs |
| [07 — Data contracts](./07-data-contracts.md) | Written |
| [08 — Limitations](./08-limitations.md) | Written |

Nothing below links to a page that does not exist.

## Reading order

**New to the project — read these three, in order:**

1. **[Architecture](./01-architecture.md)** — the four modules, what each owns, how data actually flows between them, and where the seams are.
2. **[Setup and build](./02-setup-and-build.md)** — clean clone to a running dashboard. Exact commands, in dependency order, every one of them executed before being written down.
3. **[Limitations](./08-limitations.md)** — which numbers in this repo are measurements and which are assumptions. Read before quoting anything.

**Working on the satellite stage:**

- **[03 — Remote Sensing](./03-remote-sensing.md)** — `urban_heat_analysis.js` walked section by section: the Landsat collection, the scale and offset arithmetic, cloud-mask bit twiddling, how the grid is built, what each export produces. Includes the step-by-step for running it in the Earth Engine Code Editor.

**Working on the other three modules:** their own READMEs are the current best source, and all four are unusually candid about their own limitations.

| Module | Its README |
|---|---|
| Machine Learning & Prediction | [README](../Machine%20Learning%20%26%20Prediction/README.md) · [SPEC_AUDIT](../Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md) |
| Decision-Support | [README](../Decision-Support/README.md) |
| frontend | [README](../frontend/README.md) |

## Audits

Separate from the guides. The guides describe how the project works; the audits describe how well.

| Document | Question it answers |
|---|---|
| [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md) | Does the project work as one system? What is wired to what, and where do two modules disagree? |
| [`Remote Sensing & Data Engineering/SPEC_AUDIT.md`](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md) | Does the satellite-data module meet its spec, item by item? |
| [`Machine Learning & Prediction/SPEC_AUDIT.md`](../Machine%20Learning%20%26%20Prediction/SPEC_AUDIT.md) | Same, for the modelling module. |
| [`IMPROVEMENTS.md`](../IMPROVEMENTS.md) | What is still worth doing, in priority order. |

## The shortest possible orientation

Guwahati is divided into 8,144 cells of roughly 100 m. Google Earth Engine measures each cell's temperature and vegetation. A Python rule engine ranks each cell by heat risk and assigns it a costed mitigation action. A Leaflet page draws the result twice — as it is, and as it would be after every recommendation was carried out.

The largest known problem: the vegetation index in the committed data was computed without a required rescale, so it is systematically too low, and everything derived from it is biased. The fix is in the source; the data has not been regenerated because that needs a Google Earth Engine account. [Details](./08-limitations.md).
