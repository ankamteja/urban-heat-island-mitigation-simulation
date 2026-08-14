# 05 — Decision-Support

One script, `member3_decision_support.py`, answering a question the ML module
does not: **given a fixed budget, which cells do we actually fund, and in what
order?**

```bash
cd Decision-Support
python member3_decision_support.py
```

Reads `dataset.csv` directly — it does not depend on the ML module's outputs —
and writes three CSVs beside itself.

---

## Why there are two modules that both "recommend an intervention"

Historically this was duplication, and it caused real damage. Both modules
independently decided what each cell should get, using separate copies of the
same constants. One of those copies applied a land-cover suitability filter and
the other did not — and the one that did not was the one feeding the dashboard.

The suitability rule now lives in `shared/uhi_shared.py` and both modules call
it, so **their per-cell actions are identical by construction** (a test asserts
it). The division of labour is now clean:

| | Machine Learning & Prediction | Decision-Support |
|---|---|---|
| Question | What should each cell get? | What can we afford, and what first? |
| Geometry | Full polygons | Points only (`lat`/`lon`) |
| Output | The dashboard's `grid.geojson` | Ranked CSVs for analysis |
| Cost basis | Per-cell polygon area | Flat 8,918 m² per cell |

Neither is "the" engine. The ML module owns the dashboard contract because it
carries geometry; this module owns the budget question.

---

## The pipeline

### 1. Load and validate

Resolves the dataset through `shared.source_dataset_path()` and requires
`LandCover` to be present. Renames `Latitude`/`Longitude` to `lat`/`lon` — this
module's own convention, and a difference from the ML module worth knowing when
joining the two.

Prints a derived NDVI provenance check rather than a hardcoded caveat.

> This script previously pointed at `Guwahati_Urban_Heat_Dataset.csv`, which had
> been renamed to `dataset.csv`. It crashed on every clean clone. Before that it
> pointed at `/mnt/user-data/uploads/...`, a sandbox path that never existed on
> any machine that cloned the repo. Both are why the path now has exactly one
> definition.

### 2. Map land cover

ESA WorldCover v200 codes to labels, via the shared mapping. Current
distribution:

| Land cover | Cells |
|---|---|
| tree_cover | 3,752 |
| built_up | 3,523 |
| cropland | 573 |
| water | 149 |
| grassland | 79 |
| wetland | 44 |
| bare_sparse | 24 |

### 3. Tier by Heat_Risk

Same quartile convention and the same cut points as the ML module, read from
`shared/constants.json` — they previously computed identical quartiles from two
separate hardcoded copies.

### 4. Assign actions

`shared.assign_action()`. Identical logic to the ML module; see
[04 — Machine Learning](./04-machine-learning.md#rule-3--the-action-from-land-cover-and-priority)
for the full ordering. The script asserts afterwards that nothing was assigned
to a never-touch cell.

### 5. Cost and cooling

From the shared rate table, using a flat `CELL_AREA_M2 = 8918.0`. The ML module
computes each cell's area from its own polygon instead (8,912–8,920 m²), so the
two differ by well under 0.1% per cell. That is documented in the script rather
than left to look like a disagreement.

### 6. Greedy budget-capped ranking

Sorts every actionable cell by **cooling per rupee** (`cooling_c /
cost_estimate`), assigns a rank, accumulates cost, and flags each cell as
`within_budget` until the cap is reached.

The budget is `budget_rupees` in `shared/constants.json`, currently **₹10 crore**.

At that cap, 323 of 4,157 actionable cells are funded: 249 `Tree cover` and 74
`Green park`. `Cool roof` never enters the funded set — at 60 INR/m² for 1.0 °C
it is the least cost-effective option in the catalogue, so the greedy rank puts
all 3,494 of them below the cut. That is the model working as specified, not a
bug, but it is worth stating plainly: **under this budget the recommendation is
"plant things on open land", and the 3,494 built-up cells get nothing.**

That is a direct consequence of the placeholder cooling figures. A cool roof
being 3.5× less cost-effective than a park is an assumption nobody measured.

---

## Outputs

All three are written beside the script, regardless of your working directory.
(They used to be written to the current working directory, so running the script
from anywhere else scattered three CSVs wherever you happened to be standing.)

| File | Rows | What it is |
|---|---|---|
| `recommendation.csv` | 4,157 | Every actionable cell with action, cost, cooling and cost-effectiveness. |
| `excluded.csv` | 3,987 | Every cell that gets nothing, **with the reason**. This is the audit trail for the safety rule — it is how you verify no water cell was treated. |
| `ranking.csv` | 4,157 | The same cells in funding order, with cumulative cost and the budget flag. |

Exact schemas in [07 — Data contracts](./07-data-contracts.md#contract-5--the-decision-support-outputs).

---

## Known limitation: roads

ESA WorldCover has no dedicated road class — roads are folded into `built_up`
alongside buildings. This module cannot fully guarantee "no interventions on
roads".

The mitigation is defensive rather than complete: ground-level interventions are
restricted to open-land classes and never placed on built-up cells, and built-up
cells only ever receive roof-type interventions, which are **moot rather than
harmful** if a given cell turns out to be a road. Adding an OpenStreetMap road
mask would close this properly.

---

## Structure

The script is a set of functions behind a `if __name__ == "__main__":` guard.
Previously every statement ran at module level, so merely importing it executed
the whole pipeline and wrote three CSVs as a side effect — which is why it had
no tests. It now imports cleanly, and `tests/` exercises the rules it applies.
