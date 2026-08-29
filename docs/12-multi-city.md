# 12 — Any city

This project measured one city. It now measures any city, and the dashboard
will load them side by side.

The pipeline that produced Guwahati *used to* need a Google Earth Engine
account, a browser session on Google's servers, and a hand-driven export. That
was fine for one city and impossible as a habit — and it is no longer how
anything here works. Nothing in this repository requires an account or an API
key: `backend/refresh_grid.py` re-measures the committed Guwahati grid and
`backend/build_city.py` builds new cities, both anonymously. `backend/build_city.py` does the same work
against **Microsoft Planetary Computer**, which serves the same Landsat
Collection 2 Level 2 scenes and the same ESA WorldCover tiles anonymously and
free, from a local Python process.

```bash
python backend/build_city.py --list
python backend/build_city.py --preset nagpur
python backend/build_city.py --bbox 78.42 17.36 78.54 17.46 --name Hyderabad --slug hyderabad
```

That is the whole interface. No credentials, no account, no browser.

---

## The thing that made this possible

The obstacle was believed to be `grid_id`.

`docs/00-repository-map.md` and `backend/refresh_dataset.py` both stated that
the committed dataset is the one artefact that cannot be regenerated, because
its cell ids come out of an Earth Engine vectoriser and nothing else can
reproduce them. Ids like `+102027+29089` look like opaque handles, and every
downstream file joins on them.

They are not opaque. They decode:

```
S = 100 / 111319.4908                  # Earth Engine's 100 m scale, in degrees
91.65241349286242 / S = 102027.0       # an integer, to floating-point precision
26.131093299752763 / S =  29089.0      # an integer
grid_id = f"{col:+d}{row:+d}"
```

`grid_id` is a pair of indices into a **global lattice anchored at (0, 0)**,
where the pair names the cell's south-west corner. Every city on Earth snaps to
the same lattice. Two consequences carry the entire feature:

- **A rebuild reproduces the ids exactly.** No migration, no id remapping, no
  change to a single committed Guwahati artefact, and not one existing test
  broken.
- **Cities cannot collide.** Different places occupy different lattice cells, so
  ids stay unique across the whole collection.

An advisor model, reasoning from the assumption that the ids were opaque,
recommended migrating to a new id scheme at an estimated cost of 40–60 broken
tests. It was rejected on the arithmetic above.

`tests/test_multi_city.py` pins this. Every one of the 8,144 committed ids must
decode to its own polygon's corner — and the ids and the geometry were both
produced by Earth Engine years before `build_city.py` existed, so agreement
across 8,144 independent cells is not a coincidence. The lattice constant is
written into the test as a literal rather than imported, because the builder
agreeing with its own constant would prove nothing. Changing that literal by
five parts per million fails seven tests.

---

## What a build produces

```
frontend/data/cities/<slug>/grid.geojson   # the dashboard payload, 11 properties
frontend/data/cities/<slug>/dataset.csv    # the 12-column schema of the Guwahati export
frontend/data/cities/<slug>/ranking.csv    # funding order, same order as plan_rank
frontend/data/cities/<slug>/city.json      # provenance, headline figures, grid_sha256
frontend/data/cities.json                  # the manifest, derived from the city.json files
```

`cities.json` is regenerated from whatever `city.json` files are on disk on every
build. It is never hand-edited, so it cannot claim a city the repository does not
have — the failure that once served a stale grid from a manifest nobody had
updated.

Schemas for `cities.json` and `city.json` are in
[07 — Data contracts](./07-data-contracts.md).

---

## The decision rules are not duplicated

Everything about which action a cell gets, what it costs and how much it cools
comes from `shared/uhi_shared.py`. `build_city.py` imports it and calls it.

This is deliberate and it is the single most important structural choice in the
file. [05 — Decision-Support](./05-decision-support.md) documents what happened
the last time this project had two copies of the suitability rule: they
disagreed for weeks, the difference was invisible in every aggregate the project
printed, and it took a test to find it. A second implementation of the rules
inside the city builder would have recreated that defect on a larger surface.

The remote-sensing arithmetic is likewise carried over unchanged from the Earth
Engine script: surface temperature `× 0.00341802 + 149.0 − 273.15`, surface
reflectance `× 0.0000275 − 0.2`, `QA_PIXEL` bits 1–4 rejected as cloud, and a
per-pixel median composite.

One addition the Earth Engine script did not need: surface reflectance is
**clamped to [0, 1]** before NDVI and NDBI are computed. Scaled reflectance goes
negative over water, and a negative in the denominator can flip the sign of the
ratio and make open water read as dense vegetation.

---

## Two decisions that change the numbers

### Heat_Risk bounds are per city

The Earth Engine script scales heat risk with `unitScale(LST, 20, 34)`. Those
bounds are Guwahati's, and they are silent when wrong.

Nagpur's 2nd/98th percentile surface temperatures are **40–48 °C** — entirely
above the hardcoded 34 °C ceiling. Every Nagpur cell would saturate at
`Heat_Risk = 1.0`, the quantile tiers would be cut from a constant, and the
priority map would be noise rendered in confident colours.

So each city derives its own bounds from its own 2nd/98th percentiles, rounded
outward, and records them in `city.json`. `--lst-scale 20 34` forces the original
behaviour.

The cost of this is stated plainly in
[08 — Limitations](./08-limitations.md): **priority tiers are not comparable
between cities.** "High" means hot relative to that city, and nothing else.

### The composite defaults to the local hot season

A two-year all-season median averages the hot months with the cool ones and
understates precisely the effect this project exists to measure. The default
window is the local hot season — March–June in the northern hemisphere,
November–February in the southern — and the window actually used is recorded in
`city.json`.

`--season all` overrides it.

**On reproducibility:** the default window is relative to *today*. A rebuild
next month reads a different scene list and produces different temperatures. Pin
`--start` and `--end` for a reproducible build. `city.json` always records the
window and the scene count that produced the file in front of you.

---

## The cities in the repository

| City | Region | Cells | Mean LST °C | Peak °C | Heat_Risk bounds | Scenes | Actionable | Funded at ₹10 Cr | INR rates apply |
|---|---|---:|---:|---:|:---:|---:|---:|---:|:---:|
| Ahmedabad | Gujarat, India | 8,282 | 47.91 | 57.48 | 40–53 | 8 | 6,062 | 242 | yes |
| Chennai | Tamil Nadu, India | 8,282 | 41.25 | 50.43 | 29–46 | 8 | 5,961 | 229 | yes |
| New Delhi | Delhi, India | 8,282 | 39.59 | 49.36 | 33–45 | 8 | 4,521 | 254 | yes |
| Nagpur | Maharashtra, India | 8,282 | 44.19 | 50.82 | 40–48 | 8 | 5,947 | 239 | yes |
| Phoenix | Arizona, USA | 8,282 | 48.58 | 53.10 | 42–52 | 8 | 6,189 | 267 | **no** |

Guwahati, for comparison, is 8,144 cells with a mean of 27.0 °C.

**Do not read that table as a ranking of Indian cities by heat.** Guwahati is a
single Earth Engine annual median; these are hot-season medians over eight
Landsat scenes each. Part of the gap is real and part is compositing, and this
project cannot tell you the split. See
[08 — Limitations](./08-limitations.md).

### Phoenix is in the list on purpose

Its temperatures, vegetation and land cover are measured and correct. Its rupee
figures are the Indian municipal rate card from `shared/constants.json` applied
to Arizona — arithmetic that completes without error and means nothing.

That is the case the dashboard's cost-basis banner exists for, and the reason
`city.json` carries `cost_basis_applies`. It is the worked example of a number
that is fully computed, plausibly formatted, and not true.

---

## Using it in the dashboard

The city selector in the app bar switches between everything in `cities.json`,
and `?city=<slug>` deep-links one.

**Open city file…**, or dropping a `.geojson` anywhere on the page, loads a grid
built on your own machine. The file is read with `FileReader` and parsed in the
browser; nothing is uploaded.

A dropped file is validated before anything is drawn, and every rejection names
what is actually wrong with the file — a `Point` where a `Polygon` was expected,
a missing property, a non-numeric temperature. An older 7-property grid is
rejected specifically on `plan_rank`, because that file parses, draws, and then
funds zero cells at any budget: the dashboard allocates the budget by sorting on
that integer alone, and its absence reads as "nothing qualifies" rather than as
an error.

A dropped file carries no `city.json`, so nothing vouches for where its costs
came from, and it gets an amber "costs unverified" banner rather than a green
light. Temperature and land cover are read straight from the file and stay
trustworthy either way — only the money is qualified.

---

## When it fails

| Symptom | Cause |
|---|---|
| `Unknown preset 'x'` | Run `--list`. Add an entry to `backend/city_presets.json`. |
| `No Landsat scenes ...` | The hot-season window is cloudy. Widen with `--start`/`--end`, or `--season all`. |
| `GDAL 3.5 or newer is required` | Below 3.5, `Resampling.average` averages NaN nodata into real cells silently. The check refuses rather than producing quietly wrong temperatures. |
| Scene dropped, `QA grid mismatch` | The QA band did not align with the thermal band, so cloud masking could not be trusted. The scene is dropped rather than composited unmasked. |
| Cells dropped as incomplete | Cloud, scene edge, or outside WorldCover coverage. The count is printed and recorded in `city.json`. |

A note on `pkill`: `pkill -f "build_city.py"` matches its own command line and
kills the shell that ran it. Use `pkill -f "python3 backend/build"`.

---

## See also

- [03 — Remote Sensing](./03-remote-sensing.md) — the Earth Engine path, in full.
- [07 — Data contracts](./07-data-contracts.md) — `cities.json` and `city.json`.
- [08 — Limitations](./08-limitations.md) — read before quoting any figure above.
- `tests/test_multi_city.py` — the lattice and the contract, as assertions.
