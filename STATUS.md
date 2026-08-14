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
- **129 tests pass**, and CI regenerates every artefact and fails if the
  committed copies differ.

Current recommendation set, 8,144 cells:

| Action | Cells |
|---|---|
| Cool roof | 3,494 |
| Tree cover | 589 |
| Green park | 74 |
| None | 3,987 |

Of the 3,987 excluded: 3,752 already tree cover, 149 water, 44 wetland, 42 low
priority. Total notional programme cost ₹2,141,865,191 — see the caveat on
costs below.

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
- **Two of three unit rates are unvalidated.** 150/400/1,150 INR per m² at
  25%/15%/10% coverage. Only `Green park` has a real comparable — it was revised
  from 250 on 2026-08-14, anchored on Gujarat AMRUT 2.0 municipal gardens
  (₹1,152–2,250/m²). `Tree cover` and `Cool roof` remain assumptions with no
  directly comparable municipal rate found. No tender, no survey.
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
| 1 | **Cooling values are unvalidated.** Even a crude check — do cells WorldCover calls tree cover run measurably cooler than adjacent built-up cells? — would turn an assumption into an estimate. The data to do it is already committed. | days |
| 2 | **The ₹10 crore budget funds only tree cover — 299 cells, no parks, no cool roofs.** Correct per the model, but it means the 3,494 built-up cells get nothing. Note this ordering already flipped once: the park rate was 5–9× too low, which had made parks the top-ranked option. Ranking is highly sensitive to unit rates, and two of the three are still unvalidated (item 1). | decision |
| 3 | **QGIS project has three unresolvable layers.** `guwahati_heat_project.qgz` references `./guwahati_boundary.geojson` (wrong directory), a `.shp` that exists nowhere, and an absolute path into a `Downloads/` folder on the original author's machine. Needs opening in QGIS to relink and re-save. | hour |
| 4 | **Dashboard downloads 3.7 MB to render centroids.** The renderer discards every polygon ring. A centroid-plus-bounds export would cut the payload several-fold with no visual change. | hours |
| 5 | **Land cover is not surfaced in the UI.** It now decides every recommendation; showing why a cell got its action would make the tool defensible to a planner. | hours |
| 6 | **No mobile layout, no keyboard map navigation.** | days |
| 7 | **One Landsat scene is one moment.** A pre/post-monsoon or summer/winter pair would turn a snapshot into a trend. | days |
| 8 | **Make the budget interactive.** Decision-Support already computes the ranked, budget-capped shortlist offline; exposing it as a slider is the most compelling thing this dataset can do. | days |
| 9 | **Both `SPEC_AUDIT.md` files still describe the pre-fix state** and should be folded into this document or deleted. | hour |
| 10 | **No linting or formatting config anywhere**, and no `package.json` for the frontend. All eleven JS files share global scope via `<script>` tags — `view`, `charts` and `INTERVENTIONS` are globals. ES modules plus ESLint would fix it without introducing a build step; `ruff` would cover the Python side. | hours |
| 11 | **~12 MB of the repository is duplicated or regenerable.** `frontend/data/grid.geojson` and `Machine Learning & Prediction/Results/grid.geojson` are byte-identical copies at 3.7 MB each; `Remote Sensing & Data Engineering/Results/grid.geojson` is a third 4.4 MB variant with the raw schema; `preprocessed.csv` and `tiered.csv` add ~6 MB and regenerate exactly. Only `dataset.csv` genuinely cannot be rebuilt without an Earth Engine account. Committing just that one and generating the rest in CI would shrink the repo substantially — but it would also mean a clone no longer renders the dashboard without running Python first, so it is a real trade-off, not an obvious win. | hours |
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
