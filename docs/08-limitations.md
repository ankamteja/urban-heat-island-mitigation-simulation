# 08 — Limitations

Which numbers in this project are measurements and which are assumptions.
**Read this before quoting anything from the dashboard or the CSVs.**

Nothing here is a defect. These are the honest boundaries of what the data and
the method can support. Open defects live in [`../STATUS.md`](../STATUS.md).

---

## The short version

| Number | What it actually is |
|---|---|
| Surface temperature (`LST`) | **Measured.** Landsat 8 thermal band, one scene. |
| `NDVI`, `NDBI`, `Vegetation` | **Measured.** Landsat surface reflectance. |
| `LandCover` | **Measured**, by ESA WorldCover, at 10 m, from a different sensor and a different year. |
| `Heat_Risk` | **Derived** — a closed-form function of LST and NDVI, not an independent quantity. |
| Priority tier | **A relative rank** within Guwahati, not a calibrated risk level. |
| Recommended action | **A rule**, not a prediction. No ground truth exists. |
| `cost_estimate` | **Mostly assumptions.** Only the park rate has a real comparable. |
| `cooling_c` | **An assumption.** Not measured, not fitted, not validated. |
| The "after intervention" map | **A claim about a plan**, not a forecast. |

---

## 1. Cooling values are assumptions, and they are load-bearing

The single most important caveat in the project.

| Action | Assumed cooling |
|---|---|
| Tree cover | 0.8 °C |
| Cool roof | 1.0 °C |
| Green park | 2.0 °C |

These originate in the Decision-Support intervention catalogue, whose own
comment describes them as "placeholder engineering estimates for a hackathon
demo". They are:

- **not fitted** to Guwahati LST,
- **not validated** against any field trial,
- **not adjusted** for canopy age, albedo, humidity, wind or building density,
- **flat per action**, which ignores that cooling scales with treated area and
  with how hot a cell already is.

They are load-bearing because they drive two visible outputs: the entire "after
intervention" surface, and the cost-effectiveness ranking that decides which
cells get funded. A different set of plausible numbers would produce a different
funded shortlist.

This is not hypothetical — it has already happened twice, both times via the
cost side of the same ratio.

The `Green park` rate sat at 250 INR/m², around 5–9× below every real municipal
comparable, and that single wrong number made parks the most cost-effective
option in the catalogue: the ₹10 crore budget funded 249 tree-cover cells and 74
parks. Re-anchoring it on real Gujarat AMRUT 2.0 garden projects (₹1,152–2,250/m²)
moved parks below tree cover, and the funded set became 299 cells, **all tree
cover, no parks at all**.

Then the `Cool roof` rate came down from 400 to 300 INR/m² on Telangana's Cool
Roof Policy. Cool roof is assigned to 3,494 of the 4,157 actionable cells, so it
carried 87% of the programme total: correcting it took the all-cells figure from
₹214.2 Cr to ₹167.5 Cr, moved cool roof from **last to first** on cooling per
rupee, and made the funded set **249 cells, all cool roof**.

Two unit rates, two complete reorderings of the investment priority, no change
to the satellite data or the model in between. The cooling figures have exactly
the same leverage and, unlike those two rates, still have nothing behind them.

**Fixing this is the highest-value work available.** A crude first pass — do
cells WorldCover classifies as tree cover run measurably cooler than adjacent
built-up cells? — needs no new data.

## 2. One of the three unit rates is still unvalidated

150 / 300 / 1,150 INR per m² for tree cover / cool roof / green park, at
25% / 15% / 10% coverage of a ~8,916 m² cell.

| Rate | Status |
|---|---|
| `Cool roof` 300 INR/m² | **Sourced.** Telangana's Cool Roof Policy 2023–28 — India's first — states ₹300/m² for cool roof painting or tiles, recoverable in about two years through energy savings. A state government's own figure for exactly this scope. Ahmedabad's lime wash (~₹16/m², reapplied annually) sits below it; commercial application quoted at ₹970–1,510/m² bundles waterproofing this action does not. |
| `Green park` 1,150 INR/m² | **Sourced.** Anchored on the lower of two Gujarat AMRUT 2.0 municipal garden projects (₹1,152/m² and ₹2,250/m²), deliberately, because those are ~10,000 m² civic gardens with paths, lighting and boundary walls while this action treats ~892 m² of soft landscaping. |
| `Tree cover` 150 INR/m² | **Unvalidated, but bounded below.** ≈₹3,750/tree at one tree per 25 m². Bulk Indian plantation runs ₹200–500/tree, but that is rural bulk planting without pits, guards, staking or tanker watering — not a comparable. Municipal tree-guard tenders alone have run ₹1,280–2,250 *per guard*, before the sapling, so ₹3,750/tree is not obviously wrong. It is 9% of the programme total. |

### The rates decide the answer; the model does not

The greedy ranking sorts on cooling per rupee, so the cost inputs — not the
regression — choose which cells get funded. The ordering has now flipped twice,
both times on a cost correction, and never once on a model result:

| | Ordering by cooling per rupee | ₹10 Cr funded set |
|---|---|---|
| Original | Green park > Tree cover > Cool roof | park-led |
| After the park rate was corrected | Tree cover > Green park > Cool roof | 299 tree cover cells |
| After the cool-roof rate was corrected | **Cool roof > Tree cover > Green park** | **249 cool roof cells** |

Same satellite data, same cooling assumptions, three different recommendations.
That sensitivity is the honest headline of this project: it is a cost model
wearing a machine-learning coat. Pinned in
`tests/test_suitability.py::test_cost_effectiveness_ordering_is_what_the_docs_claim`.

### Cooling is credited to the whole cell; cost is not

Cost scales with `coverage_fraction` — a cool roof is priced for 15% of a cell —
but `cooling_c` is not. The full 1.0 °C is credited to the entire ~8,918 m²
cell. That is optimistic, and it is the single largest unstated assumption left
in the pipeline: scaling cooling by coverage the way cost is scaled would take
the whole-grid mean drop from ~0.51 °C to roughly 0.1 °C.

It is left as stated rather than fixed because `cooling_c` is a placeholder to
begin with (§1) — refitting a made-up number to be more internally consistent
would buy the appearance of rigour, not rigour.

### What the totals mean

- **₹167.5 Cr** is what treating all 4,157 actionable cells would cost. It is an
  upper bound. Nothing in this repository recommends it, and for scale it is
  roughly the order of a large chunk of Guwahati Municipal Corporation's annual
  budget — not a plausible line item.
- **₹9.99 Cr** is the actual recommendation: the top 249 cells by cooling per
  rupee, in `Decision-Support/ranking.csv`. It delivers ~1.0 °C on ~2.2 km² of
  treated area, which is ~0.03 °C spread across the whole 72 km² grid.

Quote either as a scale indicator, never as a budget. No tender, no survey, no
municipal schedule of rates has been consulted for the tree-cover rate.

## 3. One scene is one moment

Every temperature in this project comes from a single Landsat 8 overpass. That
means:

- **No seasonality.** Pre-monsoon and post-monsoon Guwahati are different cities
  thermally.
- **No time of day.** Landsat crosses mid-morning. The urban heat island is
  typically strongest at night, which this data cannot see at all.
- **No trend.** A snapshot cannot show whether the problem is worsening.

## 4. Land surface temperature is not air temperature

`LST` is the radiative temperature of the ground and roof surfaces, not the air
temperature a person standing there would feel. They correlate, but not tightly,
and the offset varies with surface type — exactly the variable being
manipulated. A 2 °C modelled drop in LST is not a 2 °C drop in felt heat.

## 5. `Heat_Risk` is not an independent measurement

```
Heat_Risk = unitScale(LST, 20, 34) − unitScale(NDVI, −0.2, 0.8)
```

Verified to hold to ~1e-15 on every row. It contains no information beyond LST
and NDVI, and its scaling bounds (20–34 °C, −0.2–0.8) were chosen, not derived.
It is a convenient composite for ranking, not a risk model. This is why the
regression targets `LST`.

## 6. Priority tiers are relative, not absolute

Quantile bins: top 25% `High`, bottom 25% `Low`. **Exactly 25% of Guwahati is
High priority by construction**, and would be in any city, however cool. The
tiers say "hotter than most of Guwahati", never "dangerously hot".

## 7. The model is not used to produce anything you can see

`train_regression.py` fits a model and reports its scores, but no downstream
file depends on it. The dashboard shows measured LST, and the recommendations
come from a rule engine, not the model.

When quoting its accuracy, **use the spatial-block figure (R² 0.513), not the
random-split figure (0.895)**. On a 100 m grid adjacent cells are near
duplicates, so a random hold-out leaks most test answers through their
neighbours. The blocked split answers the question that matters — how well this
generalises to a neighbourhood it has not seen — and it is substantially less
flattering.

## 8. Recommendations are rules, not learning

There is no labelled ground truth anywhere in this project for "correct
intervention". The action assignment is an explicit, auditable decision table
over land cover and priority. That is a deliberate choice: a supervised
classifier here would be inventing authority it does not have. But it means the
recommendations are only as good as the rules, and the rules are a reasonable
first pass, not urban-planning doctrine.

## 9. ESA WorldCover has no road class

Roads are folded into the generic `built_up` category alongside buildings, so
this project **cannot guarantee "no interventions on roads"**.

The mitigation is defensive rather than complete: ground-level interventions are
restricted to open-land classes and never placed on built-up cells, and built-up
cells only ever receive roof interventions — moot rather than harmful if the
cell turns out to be a road. An OpenStreetMap road mask would close this.

WorldCover is also from a different sensor, resolution and year than the Landsat
scene, so the two are not perfectly co-registered. At 100 m cells this mostly
averages out, but boundary cells may carry the wrong class.

## 10. The `already vegetated` exclusion is blunt

3,752 cells — 46% of the study area — receive no action because WorldCover
classifies them as tree cover. Some of those are genuinely hot. The rule assumes
existing canopy means no further intervention is warranted, which is defensible
for planting but arguably wrong for a hot, sparsely-canopied cell that
WorldCover still labels tree cover.

## 11. Cell geometry is approximate

Cells are defined in degrees, not a projected CRS, so they are not exactly square
in metres: ~89.8 m × 99.3 m at this latitude, 8,912–8,920 m². The ML module
computes each cell's area from its polygon; Decision-Support uses a flat 8,918
m². The two differ by well under 0.1% per cell.

## 12. The dashboard interpolates

The heat surface is Gaussian/Shepard interpolation across cell centroids, not a
faithful rendering of 8,144 discrete measurements. Colour between cell centres
is inferred. Zoom far enough in and you are looking at an interpolation, not
data.

---

## What is *not* a limitation any more

Earlier versions of this document listed several problems that have since been
resolved. Recorded here so nobody re-derives them from an old copy:

- **NDVI is no longer uncorrected.** The Landsat C2 L2 rescale is applied
  upstream; NDVI reaches 0.781 in the committed dataset.
- **There is no proxy land-cover classifier any more.** Real ESA WorldCover
  codes are used, so the never-touch water/wetland rule now excludes real cells
  (149 water, 44 wetland) rather than being dead code.
- **Recommendations are no longer a single intervention type.** The current
  output is 3,494 `Cool roof`, 589 `Tree cover`, 74 `Green park`.
- **The two modules' cost models no longer disagree.** They read one shared rate
  table; the historical "67× disagreement" was an artifact of comparing a
  per-m²-with-coverage figure to a pre-multiplied flat rate.
- **The dashboard is not on mock data**, and its colour scale is derived from
  the loaded data rather than hardcoded.
