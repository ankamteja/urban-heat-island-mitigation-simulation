# Status

**Last verified:** 2026-08-14, by running the pipeline and querying the
committed data.

The single document describing where this project actually stands. It replaces
`IMPROVEMENTS.md` and `INTEGRATION_AUDIT.md`, which described a repository state
that no longer existed.

> **Why those were retired rather than updated.** They were honest and careful
> when written. The problem was structural: five overlapping hand-maintained
> audit documents (two `SPEC_AUDIT.md`, `IMPROVEMENTS.md`, `INTEGRATION_AUDIT.md`,
> `docs/08-limitations.md`) each described a moment in time, and the codebase
> kept moving. Each stayed individually plausible while collectively describing
> nothing that existed — which is precisely how a stale dashboard went unnoticed
> for weeks. One document, plus tests and CI that fail when reality diverges from
> it, is more trustworthy than five prose files nobody can verify.

---

## What works

- **The data is the corrected Earth Engine export.** `dataset.csv` carries NDVI
  reaching 0.781, real ESA WorldCover `LandCover`, `NDBI`, `Vegetation`, and
  real `Latitude`/`Longitude`. The re-run that four documents listed as
  outstanding had already happened.
- **Both Python modules run from a clean clone** and reproduce their committed
  outputs.
- **The dashboard serves current data**, and no cell in it recommends work on
  water, wetland, or already-forested land.
- **Both recommendation engines agree on every cell**, because they call one
  shared rule.
- **133 tests pass**, and CI regenerates every artefact and fails if the
  committed copies differ.

Current recommendation set, 8,144 cells:

| Action | Cells |
|---|---|
| Cool roof | 3,494 |
| Tree cover | 589 |
| Green park | 74 |
| None | 3,987 |

Of the 3,987 excluded: 3,752 already tree cover, 149 water, 44 wetland, 42 low
priority.

Total cost if every actionable cell were treated: **₹1,674,616,910** (~₹167.5
crore). That is an upper bound, not a proposal. The actual recommendation is the
budget-capped set in `Decision-Support/ranking.csv`: **₹9.99 crore, 249 cells,
all cool roof.** See the caveat on costs below.

---

## What was fixed, and what it cost

| Defect | Consequence | Status |
|---|---|---|
| Dataset renamed to `dataset.csv`, neither reader updated | Both Python modules crashed on any clean clone | Fixed — one definition in `shared/constants.json` |
| `preprocess.py` dropped `LandCover`, `NDBI`, `Vegetation` | The rule engine was blind to land cover | Fixed — carried through, and asserted present |
| Action table keyed on `(priority, vegetation_class)` only | **Live dashboard recommended tree planting on 148 water/wetland cells and ground works on 3,433 built-up cells** | Fixed — gated on land cover, asserted in code and tests |
| ML pipeline never re-run after the corrected export | 970 of 8,144 cells carried a stale action | Fixed — regenerated |
| `grid.geojson` copied to `frontend/data/` by hand | Undocumented step, nothing detected it being skipped | Fixed — the export writes both, a test compares them |
| `NDBI` and `Vegetation` never reached the model | Spatial-block R² of −0.02, worse than the mean | Fixed — now **+0.513** |
| Hardcoded "NDVI is UNCORRECTED" warnings | Every script contradicted the numbers printed beside it | Fixed — derived from the data |
| Duplicated constants in two modules | Nothing enforced that they agreed | Fixed — `shared/constants.json` |
| Decision-Support ran at import, wrote to the working directory | Untestable; scattered CSVs | Fixed — functions, `__main__` guard, paths relative to the script |
| Two diverged copies of the Earth Engine script | Ambiguous provenance for every number | Fixed — one canonical copy |
| `leaflet-control-geocoder` unpinned | An upstream release could break the live site | Fixed — pinned to 2.4.0 |
| Four documentation pages referenced but never written | Eight broken links | Fixed — written |
| ~12 MB of duplicated and fabricated committed data | Two byte-identical 3.7 MB grids, an unused 4.4 MB variant, a 3.3 MB regenerable intermediate, and a 900-cell fake grid that would have rendered as real if a fetch failed | Fixed — removed; the export now writes one file |

---

## What is assumed, not measured

**Read this before quoting any number from this project.**

- **Cooling values are placeholders.** 0.8 °C for tree cover, 1.0 for a cool
  roof, 2.0 for a park. They originate in the Decision-Support catalogue, whose
  own comment calls them "placeholder engineering estimates for a hackathon
  demo". Nothing is fitted to Guwahati, validated against a field trial, or
  adjusted for canopy age, albedo, humidity or wind. A flat per-action figure
  also ignores that cooling scales with treated area and with how hot a cell
  already is.
- **One of three unit rates is still unvalidated.** 150/300/1,150 INR per m² at
  25%/15%/10% coverage. `Cool roof` was revised from 400 on 2026-08-15 on
  Telangana's Cool Roof Policy 2023–28 (₹300/m² for cool roof painting or
  tiles); `Green park` from 250 on 2026-08-14 on Gujarat AMRUT 2.0 municipal
  gardens (₹1,152–2,250/m²). `Tree cover` remains an assumption — no all-in
  urban municipal per-tree rate was found, though municipal tree-guard tenders
  alone run ₹1,280–2,250 per guard, which puts a floor under it. No tender, no
  survey for that one.
- **The rates decide the answer, not the model.** Cooling per rupee has been
  reordered twice, both times by a cost correction and never by a model result,
  and each reordering replaced the funded set wholesale. Cool roof currently
  leads tree cover by 4% — inside the error of an unvalidated rate.
- **The "after intervention" map is a claim, not a forecast.** It shows what the
  plan asserts it would achieve.
- **Quote the spatial-block R² (0.513), never the random-split figure (0.895)
  alone.** Adjacent 100 m cells are near-duplicates, so a random split leaks most
  test answers through their neighbours.
- **Priority tiers are relative ranks within Guwahati**, not calibrated absolute
  risk levels.
- **ESA WorldCover has no road class.** Roads sit inside `built_up`, so "no
  interventions on roads" is mitigated defensively (built-up cells only ever get
  roof work) rather than guaranteed.

---

## Open

| # | Item | Effort |
|---|---|---|
| 1 | **Cooling values are not intervention-validated.** The new reproducible nearby-cell check finds existing tree cover 0.70 °C cooler than matched built-up cells in this one scene, but it is cross-sectional and cannot estimate the effect of planting trees. Cool roofs and parks still have no empirical check. | field study |
| 2 | **The ₹10 crore budget funds only cool roofs — 249 cells, no trees, no parks.** Correct per the model, but it means the 589 open-land cells get nothing. This ordering has now flipped twice, both times on a rate correction: the park rate was 5–9× too low, then the cool-roof rate was 33% too high. Cool roof now leads tree cover by just 4%, and the tree-cover rate is still unvalidated (item 1). Treat the funded set as approximately right, not decisively right. | decision |
| 3 | **QGIS project has three unresolvable layers.** `guwahati_heat_project.qgz` references `./guwahati_boundary.geojson` (wrong directory), a `.shp` that exists nowhere, and an absolute path into a `Downloads/` folder on the original author's machine. Needs opening in QGIS to relink and re-save. | hour |
| 4 | **Dashboard downloads 3.7 MB to render centroids.** The renderer discards every polygon ring. A centroid-plus-bounds export would cut the payload several-fold with no visual change. | hours |
| 5 | **Land cover is not surfaced in the UI.** It now decides every recommendation; showing why a cell got its action would make the tool defensible to a planner. | hours |
| 6 | **No mobile layout, no keyboard map navigation.** | days |
| 7 | **One Landsat scene is one moment.** A pre/post-monsoon or summer/winter pair would turn a snapshot into a trend. | days |
| 8 | **Make the budget interactive.** Decision-Support already computes the ranked, budget-capped shortlist offline; exposing it as a slider is the most compelling thing this dataset can do. | days |
| 9 | **Both `SPEC_AUDIT.md` files still describe the pre-fix state.** They now carry a superseded banner pointing here, but were left in place rather than deleted — they are other contributors' module documentation and may hold detail worth folding in first. | hour |
| 13 | **Three top-level directories contain spaces and an ampersand** (`Machine Learning & Prediction`, `Remote Sensing & Data Engineering`). Every cross-reference is URL-encoded (`%20%26%20`), scripts quote paths defensively, and CI needs quoted `working-directory` keys. Renaming to `ml/`, `remote-sensing/` would be cleaner but touches ~40 files, the CI workflows, `.vercelignore` and `shared/uhi_shared.py` for a cosmetic payoff. **Deliberately not done** — it needs a decision, not a drive-by. | decision |
| 10 | **No linting or formatting config anywhere**, and no `package.json` for the frontend. All eleven JS files share global scope via `<script>` tags — `view`, `charts` and `INTERVENTIONS` are globals. ES modules plus ESLint would fix it without introducing a build step; `ruff` would cover the Python side. | hours |
| 12 | **46% of the study area now receives no action by design.** The `already_green` rule excludes all 3,752 cells ESA WorldCover classifies as tree cover, including hot ones. This is the single largest behavioural change from the land-cover fix and is defensible for *planting*, but arguably wrong for a hot, sparsely-canopied cell that WorldCover still labels tree cover. Worth a deliberate decision rather than inheriting it. | decision |

---

## Verifying any of this yourself

```bash
pip install -r "Machine Learning & Prediction/requirements.txt" pytest
pytest tests/ -v
```

The tests assert the claims above rather than restating them: that the source
dataset resolves, that its NDVI is the corrected range, that no committed
dashboard cell recommends work on water, that the grid is not stale, and that
both engines agree cell by cell.
