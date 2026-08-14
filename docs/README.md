# Documentation

Everything needed to understand, build, run and modify this project.

## The shortest possible orientation

Guwahati is divided into 8,144 cells of roughly 100 m. Google Earth Engine
measures each cell's surface temperature, vegetation and land cover. A Python
rule engine ranks each cell by heat risk and assigns it a costed mitigation
action, refusing to place work on water, wetland or already-forested land. A
Leaflet page draws the result twice — as it is, and as it would be after every
recommendation was carried out.

The largest remaining caveat: the cooling figures behind the "after" map are
planning assumptions, not measurements. See [08 — Limitations](./08-limitations.md).

---

## Pages

| Page | What it covers |
|---|---|
| [00 — Repository map](./00-repository-map.md) | **What every folder and file is**, who writes it, who reads it, and which files are generated. |
| [01 — Architecture](./01-architecture.md) | The four modules, what each owns, how data flows, and where the seams are. |
| [02 — Setup and build](./02-setup-and-build.md) | Clean clone to a running dashboard, in dependency order. |
| [03 — Remote Sensing](./03-remote-sensing.md) | The Earth Engine script section by section, and how to run it. |
| [04 — Machine Learning](./04-machine-learning.md) | The four ML scripts, every threshold, and which model score to quote. |
| [05 — Decision-Support](./05-decision-support.md) | Budget-constrained ranking, and why there are two modules. |
| [06 — Frontend](./06-frontend.md) | The dashboard's files and how the heat surface is actually drawn. |
| [07 — Data contracts](./07-data-contracts.md) | Every schema, who writes it, who reads it, what breaks if it changes. |
| [08 — Limitations](./08-limitations.md) | Which numbers are measurements and which are assumptions. |
| [09 — Automated refresh](./09-automated-refresh.md) | How the satellite data keeps itself current, and the one-time setup to enable it. |

## Reading order

**New to the project:**

1. [00 — Repository map](./00-repository-map.md) — get oriented in the file tree.
2. [01 — Architecture](./01-architecture.md) — how the pieces relate.
3. [02 — Setup and build](./02-setup-and-build.md) — get it running.
4. [08 — Limitations](./08-limitations.md) — read before quoting any number.

**Changing the pipeline:** [07 — Data contracts](./07-data-contracts.md) first.
It is the page that would have prevented this project's two worst defects.

**Changing the dashboard:** [06 — Frontend](./06-frontend.md), then the contract
section of [07](./07-data-contracts.md#contract-4--gridgeojson-the-frontend-contract).

---

## Status

Project status lives in one place: [`../STATUS.md`](../STATUS.md) — what works,
what is assumed, what is still open, and how to verify each claim.

It replaced `IMPROVEMENTS.md` and `INTEGRATION_AUDIT.md`. Those were honest when
written, but five overlapping hand-maintained audit documents drifted out of
sync with a codebase that kept moving, and each stayed individually plausible
while collectively describing a repository that no longer existed. The guides
above describe how the project works; `STATUS.md` plus `tests/` describe how
well, and the tests fail when the claims stop being true.

Each module also carries its own `README.md`:

| Module | README |
|---|---|
| Remote Sensing & Data Engineering | [README](../Remote%20Sensing%20%26%20Data%20Engineering/README.md) |
| Machine Learning & Prediction | [README](../Machine%20Learning%20%26%20Prediction/README.md) |
| Decision-Support | [README](../Decision-Support/README.md) |
| frontend | [README](../frontend/README.md) |
