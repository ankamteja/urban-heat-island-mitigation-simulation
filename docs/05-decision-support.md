# 5. Decision-Support

This module answers one question: **given a fixed pot of money, in what order should the city spend it?** It is one Python file — [`Decision-Support/member3_decision_support.py`](../Decision-Support/member3_decision_support.py) — that reads the same 8,144-cell satellite table everything else reads, decides which cooling intervention is legal on each cell, scores each cell by *degrees of cooling bought per rupee spent*, sorts the whole city descending by that score, walks down the sorted list adding up costs, and stops when it hits ₹50,00,000. It writes three CSVs. This page walks that file top to bottom, defines every term it needs, justifies every constant in it with numbers taken from the committed data, and then shows you what the output actually contains — including three things about the current run that the code's own comments do not tell you.

## Contents

- [The question, and how it differs from the ML module's](#the-question-and-how-it-differs-from-the-ml-modules)
- [Vocabulary you need first](#vocabulary-you-need-first)
- [How to run it](#how-to-run-it)
- [The script, section by section](#the-script-section-by-section)
  - [§1 Configuration and constants](#1-configuration-and-constants)
  - [§2 Path resolution — the fix that made this module runnable](#2-path-resolution--the-fix-that-made-this-module-runnable)
  - [§3 `extract_centroid` and shapely](#3-extract_centroid-and-shapely)
  - [§4 `proxy_land_cover` and why a *quantile* proxy](#4-proxy_land_cover-and-why-a-quantile-proxy)
  - [§5 `load_data` — assembling the table](#5-load_data--assembling-the-table)
- [The intervention catalogue](#the-intervention-catalogue)
- [The suitability filter and the per-cell choice](#the-suitability-filter-and-the-per-cell-choice)
- [What actually comes out: three consequences](#what-actually-comes-out-three-consequences)
- [The greedy ranking](#the-greedy-ranking)
- [The cost-model conflict](#the-cost-model-conflict)
- [The three output files](#the-three-output-files)
- [What to fix, in order](#what-to-fix-in-order)
- [Where to next](#where-to-next)

---

## The question, and how it differs from the ML module's

Two modules in this project read `Guwahati_Urban_Heat_Dataset.csv` and both emit something that looks like "what should we do about this cell." They are not the same question, and it is worth being precise about the difference before reading either.

| | Machine Learning & Prediction | Decision-Support |
|---|---|---|
| Question | *What should happen to each cell?* | *Given ₹50,00,000, in what order do we spend it?* |
| Output shape | Every cell labelled with a priority tier and an action | Every cell scored, sorted, and marked funded / not funded |
| Budget-aware | No | Yes — this is the whole point |
| Key script | [`tier_and_recommend.py`](../Machine%20Learning%20%26%20Prediction/scripts/tier_and_recommend.py) | `member3_decision_support.py` |

The ML module assigns each cell an action with no notion of a budget; it will happily recommend work on all 8,144 cells and total the bill (~₹1.6 billion). Decision-Support starts from the opposite end: the money is fixed and small, so the only interesting output is an *ordering*.

**They overlap, and they were built in parallel without coordination.** Say this plainly in any report: two people independently wrote a per-cell intervention recommender against the same input, using different column names, different action vocabularies (`trees` vs `Tree cover`), and — see [the cost-model conflict](#the-cost-model-conflict) — cost models that disagree by up to 67×. Neither is wrong on its own terms. But the project has one dashboard, and it is fed by the ML module's schema, not this one's. See [`01-architecture.md`](./01-architecture.md#what-each-module-owns) for how the boundary was eventually drawn, and [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md) findings 2 and 3 for the audit that surfaced it.

## Vocabulary you need first

Every term this page uses, in one sentence each. No GIS or operations-research background is assumed.

| Term | Meaning |
|---|---|
| **Grid cell** | One ~100 m patch of Guwahati. The unit of everything in this project. There are 8,144. |
| **GeoJSON** | A plain-text format, written in JSON, for describing shapes on the Earth's surface — points, lines, polygons — as lists of longitude/latitude coordinate pairs. |
| **shapely** | A Python library for geometry: give it a shape and it can compute that shape's area, its centre, whether it overlaps another shape, and so on. It knows nothing about maps or projections; it does plane geometry on whatever coordinates you hand it. |
| **Centroid** | The geometric centre of a shape — the average position of every point inside it. For a rectangle, exactly the middle. Used here to collapse each cell's four-corner polygon down to a single (latitude, longitude) point. |
| **NDVI** | Normalized Difference Vegetation Index: a number from −1 to +1 measuring how much living green vegetation a patch of ground contains. Higher means greener. Produced upstream — see [`03-remote-sensing.md`](./03-remote-sensing.md). |
| **LST** | Land Surface Temperature: the temperature of the ground itself, in °C, as read by the satellite's thermal sensor. Not air temperature. |
| **Quantile** | A cut point that divides sorted data into equal-sized groups. The 0.25 quantile (also called the first quartile, `q1`) is the value below which 25% of the data falls. The 0.75 quantile (`q3`) is the value below which 75% falls. |
| **Proxy classifier** | A stand-in rule that guesses a label you don't actually have, using something you *do* have. Here: guessing land-cover type from NDVI, because the real land-cover column doesn't exist in the data yet. |
| **Cost-effectiveness ratio** | Benefit divided by cost. Here: degrees Celsius of cooling per rupee spent, written `cooling_per_rupee` in the code. Higher is better value. |
| **Greedy algorithm** | A method that repeatedly takes whatever looks best *right now*, never reconsidering an earlier choice. Fast and easy to explain; not guaranteed to find the best overall answer. |
| **Knapsack problem** | The classic optimisation problem this module deliberately doesn't solve: given items each with a cost and a value, and a fixed budget, choose the subset with the highest total value. Solving it exactly requires dynamic programming; a greedy ratio sort only approximates it. |

## How to run it

The module needs `pandas`, `numpy` and `shapely`. It reads the Remote Sensing module's committed CSV and writes its three outputs next to itself.

```bash
pip install pandas numpy shapely
python "Decision-Support/member3_decision_support.py"
```

You can run it from anywhere in the repo — every path it touches is resolved relative to the script file, not to your shell's working directory. See [§2](#2-path-resolution--the-fix-that-made-this-module-runnable) for why that sentence needed writing down.

It prints its progress, then the resolved output paths, then the top five rows of the ranking. It takes a few seconds; there is no model to train and nothing to download.

---

## The script, section by section

### §1 Configuration and constants

Everything tunable sits in one block at the top:

```python
USE_SYNTHETIC = False
USE_PROXY_LANDCOVER = True   # flip to False once Member 1 adds real land_cover column
GRID_CELL_AREA_M2 = 100 * 100

BUDGET_RUPEES = 5_000_000
```

**`USE_SYNTHETIC`** switches the input between the real dataset and a randomly generated 400-cell fake city defined inside `load_data()`. It is `False`, so the real data is used. Don't dismiss the synthetic branch as scaffolding, though — it is the only place in this module where the full intervention catalogue is actually exercised, and it explains the design of everything below. More on that in [the catalogue section](#the-intervention-catalogue).

**`USE_PROXY_LANDCOVER`** is the single most consequential flag in the file. The input CSV has no land-cover column — no field saying "this cell is a road" or "this cell is a building." When this flag is `True`, the script invents a three-class stand-in from NDVI. When it is `False`, it expects a real `LandCover` column that does not yet exist. It is `True`.

**`BUDGET_RUPEES = 5_000_000`** — ₹50 lakh, the total money available. There is no municipal budget document behind this number; it is a plausible round figure for a pilot programme, chosen so the ranking has to actually cut somewhere rather than fund everything. Note what it buys: at ₹5,000 per tree-planting cell, ₹5,000,000 funds **exactly 1,000 cells**. The suspiciously round "top 1,000" in the output is not a coincidence, it is `5_000_000 ÷ 5_000`.

**`GRID_CELL_AREA_M2 = 100 * 100`** — 10,000 m², the nominal area of one grid cell, from the "100 m grid" the Earth Engine script builds. Two things to know about it:

1. **It is never read.** Grep the file: it is written once, at line 183, into `pocket_park`'s spec as `"min_cell_area_m2": GRID_CELL_AREA_M2`, and no code anywhere consults that key. `suitable_interventions_for_cell()` filters on `allowed_land_cover` and nothing else. It is a documented intention — *don't put a park in a cell too small for one* — that was never wired up. It is doubly moot because `pocket_park`'s allowed list is empty under the proxy anyway.
2. **It is wrong on its own terms.** The cells are 0.00089832° squares in EPSG:4326, which at Guwahati's latitude of 26.13° works out to roughly 89.8 m × 99.3 m ≈ 8,917 m², not 10,000. The ML module computes real per-cell areas from the polygon bounds; this constant assumes the nominal figure. See the structural caveats in [`08-limitations.md`](./08-limitations.md#structural-caveats).

Neither point affects any committed output, precisely because the constant is dead. But if you ever wire the area check up, fix the value first.

### §2 Path resolution — the fix that made this module runnable

```python
MODULE_DIR = Path(__file__).resolve().parent
REPO_DIR = MODULE_DIR.parent
SOURCE_CSV = (
    REPO_DIR
    / "Remote Sensing & Data Engineering"
    / "Dataset"
    / "Guwahati_Urban_Heat_Dataset.csv"
)   # Member 1's real export

RECOMMENDATION_CSV = MODULE_DIR / "recommendation.csv"
EXCLUDED_CSV = MODULE_DIR / "excluded.csv"
RANKING_CSV = MODULE_DIR / "ranking.csv"
```

`__file__` is the path to the script itself. `.resolve()` turns it into an absolute path with any symlinks and `..` segments flattened out. `.parent` then gives the directory containing it — and since this file sits directly in `Decision-Support/`, that directory *is* the module directory, and one more `.parent` is the repository root. Every input and output path is built from those two anchors with the `/` operator, which `pathlib.Path` overloads to mean "join a path segment."

The effect: the script's behaviour does not depend on your shell's working directory. `python Decision-Support/member3_decision_support.py` and `python member3_decision_support.py` from inside the folder both read the same input and write to the same three places.

**Contrast with the earlier state (now fixed).** This is worth spelling out because it is why nobody could check this module's numbers for so long. As recorded in [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md) finding 4, the script previously hard-coded:

```python
DATASET_CSV = "/mnt/user-data/uploads/Guwahati_Urban_Heat_Dataset.csv"
```

That is a sandbox upload path from whatever throwaway environment the script was first written in. It exists nowhere in this repository and nowhere on any machine that clones it. The consequence was not cosmetic: **the module could not be executed from a clean clone at all**, so its committed CSVs could not be regenerated, re-derived, or verified against the code that supposedly produced them. The audit had to trace the logic by hand. Path resolution is now relative to the file, and this is closed.

One more piece of defensive work, immediately after:

```python
    if not SOURCE_CSV.exists():
        raise FileNotFoundError(
            f"Source dataset not found: {SOURCE_CSV}\n"
            "Expected the Remote Sensing & Data Engineering module's exported CSV.\n"
            "Set USE_SYNTHETIC = True to run this module on synthetic data instead."
        )
```

The comment above it explains the reasoning: *"Fail loudly and explanatorily rather than letting pandas raise a bare FileNotFoundError on a path the reader has no context for."* Without this, `pd.read_csv` throws a one-line error naming a path the reader has never seen, with no hint about which module was supposed to produce it or what the workaround is. Three lines of message turn a dead end into an instruction.

### §3 `extract_centroid` and shapely

The upstream CSV does not carry latitude and longitude columns. It carries a column literally named `.geo` holding, for each cell, a GeoJSON polygon as a string. One row's value looks like this (whitespace added for readability):

```json
{"geodesic": false, "type": "Polygon", "coordinates": [[
  [91.65241349286242, 26.131093299752763],
  [91.65331180814654, 26.131093299752763],
  [91.65331180814654, 26.13199161503688],
  [91.65241349286242, 26.13199161503688],
  [91.65241349286242, 26.131093299752763]]]}
```

Five coordinate pairs describing a rectangle — four corners plus a repeat of the first to close the ring. Each pair is `[longitude, latitude]`, in that order, which is the GeoJSON convention and the opposite of how people say it aloud.

The map needs a point, not a polygon, so:

```python
def extract_centroid(geo_str):
    """Parse the .geo GeoJSON string GEE exports and return (lat, lon) centroid."""
    try:
        geom = shape(json.loads(geo_str))
        c = geom.centroid
        return pd.Series([c.y, c.x], index=["lat", "lon"])
    except Exception:
        return pd.Series([np.nan, np.nan], index=["lat", "lon"])
```

Line by line:

- `json.loads(geo_str)` turns the text into a Python dictionary.
- `shape(...)` is shapely's constructor that reads a GeoJSON-shaped dictionary and returns a real geometry object — here a `Polygon`. This is the one and only thing shapely is used for in this module.
- `geom.centroid` computes the geometric centre. For an axis-aligned rectangle that is simply the midpoint of the diagonals, but shapely computes it in general for any polygon.
- `c.y, c.x` — shapely stores coordinates as `x` then `y`, i.e. longitude then latitude, matching GeoJSON's order. The return deliberately swaps them so the resulting columns come out as `lat, lon`, which is how the rest of the pipeline and every mapping library names them. **This swap is the single most likely place to introduce a silent bug** if you edit this function: mixing up `x`/`y` here puts Guwahati in the Indian Ocean, and nothing downstream would object.
- Returning a `pd.Series` with a two-element index is what lets the caller do `df.join(df[".geo"].apply(extract_centroid))` and get two new columns in one pass, rather than calling the parser twice.
- The bare `except Exception` returning two `NaN`s (Not a Number — pandas' missing-value marker) means one malformed row cannot abort a run over 8,144 rows. The cost is that a systematically broken `.geo` column would produce a table full of `NaN` rather than an error. Acceptable here because the coordinates are only carried through to the output for mapping; no arithmetic depends on them.

A note on tooling: the module spec named GeoPandas, and this uses `shapely` directly. GeoPandas is essentially pandas with a geometry column and coordinate-system awareness bolted on. Since this module does no spatial joins and no reprojection — it wants a centroid and nothing else — the direct shapely call is functionally equivalent and one dependency lighter. It is flagged in [`Decision-Support/README.md`](../Decision-Support/README.md) as a spec-tools gap, not a correctness gap.

### §4 `proxy_land_cover` and why a *quantile* proxy

Every suitability rule in this module is a rule about land cover: don't plant trees in a lake, don't build a park on a highway. And the input data has no land-cover column. That gap is filled here:

```python
def proxy_land_cover(row, ndvi_q1, ndvi_q3):
    """
    Stand-in classifier until real WorldCover land_cover lands (Member 1 audit item D).
    Uses QUANTILE thresholds (top/bottom 25% of this dataset's own NDVI distribution)
    instead of fixed values - this stays correct whether NDVI is the current
    compressed/buggy version (audit item #3) or Member 1's eventual fixed version,
    since it always splits relative to what's actually in the data.
    Cannot distinguish road/building/parking (all read as 'low NDVI' from satellite
    alone) - that's exactly why pond/park placement waits for real land cover.
    """
    ndvi = row["ndvi"]
    if ndvi >= ndvi_q3:
        return "vegetated"
    elif ndvi >= ndvi_q1:
        return "moderate"
    else:
        return "bare_or_built_hot"
```

Three classes, cut at the quartiles of this dataset's own NDVI distribution: greenest 25% is `vegetated`, least green 25% is `bare_or_built_hot`, the middle 50% is `moderate`.

**Why quantiles and not fixed thresholds.** The textbook approach would be absolute cut points — say, NDVI above 0.3 is vegetation. That would be catastrophic on this data, and the reason is the project's largest known defect. The Earth Engine script originally computed NDVI from Landsat Collection 2 Level 2 digital numbers without applying the required `× 0.0000275 − 0.2` rescale. The multiplier cancels out of a normalized difference; **the `− 0.2` offset does not**. Every NDVI value in the committed data is therefore systematically compressed toward zero. Measured across all 8,144 cells:

```
NDVI   min −0.096921   median 0.179465   max 0.386438
```

A city with Guwahati's tree cover and surrounding hills should reach 0.7–0.85. An absolute threshold of 0.3 would classify essentially the entire city as bare — the maximum NDVI in the whole dataset is 0.386. Full detail in [`08-limitations.md`](./08-limitations.md#the-one-that-matters-most-ndvi-in-the-committed-data-is-wrong).

A quantile split is immune to this. It never asks "is this cell green in absolute terms," only "is this cell green *relative to the rest of this city*." Both the buggy NDVI and the eventual corrected NDVI are monotonic in true greenness — a greener cell always gets a higher number in either version — so the ranking, and therefore the quartile split, is essentially unchanged by the fix. The proxy will keep producing sensible relative classes on the day the data is regenerated, with no code change. The same trick is used for the ML module's priority tiers, for the same reason.

**Worked numbers from the committed dataset.** The quartile cut points of the NDVI column are `q1 ≈ 0.1279` and `q3 ≈ 0.2307` (computed from the dataset's NDVI column with the same linear interpolation pandas' `.quantile()` uses; the script prints its own values at runtime). So:

| Class | Rule | Cells | Share |
|---|---|---:|---:|
| `vegetated` | NDVI ≥ 0.2307 | 2,036 | 25% |
| `moderate` | 0.1279 ≤ NDVI < 0.2307 | 4,072 | 50% |
| `bare_or_built_hot` | NDVI < 0.1279 | 2,036 | 25% |

Those counts are not estimates — they are countable straight out of the committed `recommendation.csv` and `excluded.csv`, and they come to exactly 25/50/25% of 8,144 because that is what a quartile split does by construction.

**What the proxy fundamentally cannot do**, as the docstring says outright: it cannot tell a road from a building from a parking lot from bare soil. From NDVI alone all four are simply "not green." That single limitation drives almost every design decision in the rest of the file, and it is the direct cause of two of [the three consequences](#what-actually-comes-out-three-consequences) below.

### §5 `load_data` — assembling the table

The real-data branch is five lines of substance:

```python
    df = pd.read_csv(SOURCE_CSV)
    print(f"Loaded {len(df)} rows from {SOURCE_CSV}")
    df = df.join(df[".geo"].apply(extract_centroid))
    df = df.rename(columns={"LST": "predicted_temp", "NDVI": "ndvi"})

    if USE_PROXY_LANDCOVER:
        q1, q3 = df["ndvi"].quantile([0.25, 0.75])
        print(f"Proxy NDVI thresholds (this run): bottom 25% < {q1:.3f}, top 25% >= {q3:.3f}")
        df["land_cover"] = df.apply(proxy_land_cover, axis=1, ndvi_q1=q1, ndvi_q3=q3)
    else:
        if "LandCover" in df.columns:
            df = df.rename(columns={"LandCover": "land_cover"})
```

Read the CSV; parse centroids into `lat`/`lon`; rename two columns; derive the proxy class.

The rename hides an honest substitution worth flagging. The column is called **`predicted_temp`**, but the value assigned to it is `LST` — the satellite's *measured* temperature, not a model's prediction. The intended source was the ML module's `predictions.csv`, which was not available when this was written. It is a legitimate stand-in and the ranking logic is genuinely agnostic to where the temperature came from, but the column name says "predicted" and the number is a measurement. Don't let that slip into a methods section unqualified.

Note also that `q1, q3` are computed **once, over the whole dataset**, then passed into every row's classification. The thresholds are properties of the city, not of the cell. Running this on a subset of Guwahati would produce different thresholds and therefore different classes for the same cells — which is the correct behaviour for a relative measure, but means the classes are not comparable across runs on different inputs.

---

## The intervention catalogue

Four cooling interventions, each with a cost, an expected cooling effect, and a list of land-cover classes it is permitted on:

```python
INTERVENTIONS = {
    "trees": {
        "cost_per_cell": 5_000,
        "cooling_c": 0.8,
        # works on proxy categories now; add "hillslope" back once real land cover lands
        "allowed_land_cover": ["moderate", "bare_or_built_hot",
                                "vacant", "residential", "park", "hillslope"],
    },
    "pocket_park": {
        "cost_per_cell": 400_000,
        "cooling_c": 2.0,
        # deliberately NOT enabled on proxy data - proxy can't confirm a cell is
        # actually open/vacant land vs. a road or building. Real land_cover required.
        "allowed_land_cover": [] if USE_PROXY_LANDCOVER else ["vacant"],
        "min_cell_area_m2": GRID_CELL_AREA_M2,
    },
    "green_roof": {
        "cost_per_cell": 150_000,
        "cooling_c": 1.5,
        # same reasoning - needs confirmed building footprints, not proxy
        "allowed_land_cover": [] if USE_PROXY_LANDCOVER else ["building_dense"],
    },
    "cool_roof": {
        "cost_per_cell": 30_000,
        "cooling_c": 1.0,
        # safe on proxy: even if we can't tell building vs bare ground, a reflective
        # coating recommendation just becomes moot (not harmful) if it's not a roof -
        # unlike a pond, which would be actively wrong if placed on a road
        "allowed_land_cover": ["moderate", "bare_or_built_hot",
                                "building_dense", "residential"],
    },
}

NEVER_TOUCH = ["road", "highway", "water", "wetland"]
```

Summarised:

| Intervention | `cost_per_cell` | `cooling_c` | Allowed on (under the proxy, `USE_PROXY_LANDCOVER = True`) | Ratio, °C per ₹ |
|---|---:|---:|---|---:|
| `trees` | ₹5,000 | 0.8 °C | `moderate`, `bare_or_built_hot` (plus four classes the proxy never emits) | 1.6e-4 |
| `pocket_park` | ₹400,000 | 2.0 °C | *nothing* — list is empty by design | 5.0e-6 |
| `green_roof` | ₹150,000 | 1.5 °C | *nothing* — list is empty by design | 1.0e-5 |
| `cool_roof` | ₹30,000 | 1.0 °C | `moderate`, `bare_or_built_hot` (plus `residential`, `building_dense`, never emitted) | 3.3e-5 |

### Justifying each number

**The `cooling_c` values — 0.8, 2.0, 1.5, 1.0 °C.** These are this module's own assumptions, and the file says so in a comment directly above the dict: *"Numbers are placeholder engineering estimates for a hackathon demo."* They are plausible orders of magnitude from the urban-cooling literature — a park cools more than a tree canopy, which cools more than a reflective roof coating, which is more than nothing — and their *relative ordering* is defensible. None of them is modelled, fitted, or measured for Guwahati. Nothing supersedes them: they are also the source of the `COOLING_C` values in the ML module, which imported them by name and labelled them as borrowed. Present them as assumptions and no one will object; present them as findings and you will deserve what follows.

**The `cost_per_cell` values — ₹5,000 / ₹400,000 / ₹150,000 / ₹30,000.** Flat per-cell placeholders. These are the numbers you must **not quote to anyone**, for reasons given in [the cost-model conflict](#the-cost-model-conflict) below. Internally they are still load-bearing, because the ranking depends on the *ratios* between them, and the file's comment is explicit about the consequence of touching them: *"Do not change the numbers - changing any of them reorders the greedy ranking."*

**The `allowed_land_cover` lists.** Read these against the three classes the proxy can actually produce — `vegetated`, `moderate`, `bare_or_built_hot` — and their design becomes clear:

- `trees` lists six classes, but only `moderate` and `bare_or_built_hot` are reachable today. `vacant`, `residential`, `park` and `hillslope` are there for the real-land-cover future (and for the synthetic branch, which does emit them).
- `pocket_park` and `green_roof` use `[] if USE_PROXY_LANDCOVER else [...]` — a conditional that hands them an **empty list**, meaning no cell qualifies, whenever the proxy is in use. This is a deliberate switch-off, not an oversight. The reasoning in the comment is the right one: a park or pond placed on what turns out to be a road is *actively wrong*, and the proxy cannot rule that out.
- `cool_roof` is left enabled on proxy classes on the opposite reasoning: recommending a reflective coating on something that turns out not to be a roof is *moot*, not harmful. The failure mode is a wasted recommendation, not a dangerous one.

That is a genuinely good risk-asymmetry argument, and worth stating in a pitch: the module disables what could be wrong and keeps what could merely be useless.

**`NEVER_TOUCH = ["road", "highway", "water", "wetland"]`.** A hard veto, checked before anything else: if a cell's land cover is in this list, it gets no intervention at all, regardless of how hot or how cheap. The list is correct and the code implementing it is correct. It also does nothing at all on the current data — see [consequence 3](#3-never_touch-excludes-zero-cells).

**Where the catalogue is fully alive.** If you want to see the four interventions and `NEVER_TOUCH` actually working, set `USE_SYNTHETIC = True`. That branch generates a fake 400-cell city whose land covers are drawn from a nine-class list:

```python
        land_covers = rng.choice(
            ["residential", "vacant", "road", "highway", "water", "wetland",
             "hillslope", "building_dense", "park"],
            size=n,
            p=[0.28, 0.16, 0.10, 0.06, 0.04, 0.06, 0.10, 0.14, 0.06],
        )
```

`road`, `highway`, `water` and `wetland` are all present, so `NEVER_TOUCH` bites; `building_dense` is present, so `cool_roof` has a class where `trees` is not allowed and can finally win. This is the world the catalogue was written for. The real data is not that world yet.

## The suitability filter and the per-cell choice

Two functions. The first answers "what is legal here":

```python
def suitable_interventions_for_cell(land_cover):
    """Return list of intervention names legally/physically valid for this cell."""
    if land_cover in NEVER_TOUCH:
        return []
    return [
        name for name, spec in INTERVENTIONS.items()
        if land_cover in spec["allowed_land_cover"]
    ]
```

The veto first, then a list comprehension keeping every intervention whose `allowed_land_cover` contains this cell's class. Note there is no scoring here at all — this is a pure legality filter, and separating it from the scoring is what makes the module auditable. You can point at a cell and say exactly why an option was or was not on the table.

The second picks the winner among the legal options:

```python
def best_intervention_for_cell(row):
    """..."""                       # docstring elided
    options = suitable_interventions_for_cell(row["land_cover"])
    if not options:
        reason = ("already vegetated - no action needed"
                   if row["land_cover"] == "vegetated"
                   else "excluded (never-touch land cover)")
        return pd.Series([None, None, None, None, reason],
                          index=["intervention", "cost_rupees", "cooling_c",
                                 "cooling_per_rupee", "exclusion_reason"])

    best = None
    for name in options:
        spec = INTERVENTIONS[name]
        cpr = spec["cooling_c"] / spec["cost_per_cell"]
        # Slightly favor cells that are already hotter and low-NDVI (more room to improve)
        heat_priority_boost = 1 + max(0, (row["predicted_temp"] - 35)) * 0.02
        adjusted_cpr = cpr * heat_priority_boost
        if best is None or adjusted_cpr > best[3]:
            best = (name, spec["cost_per_cell"], spec["cooling_c"], adjusted_cpr)
```

If no option is legal, the cell is not silently dropped — it gets a recorded reason and lands in `excluded.csv`. Two reasons exist: a `vegetated` cell is already green and needs nothing, and any other empty-options cell was vetoed by `NEVER_TOUCH`.

Otherwise the loop computes, for each legal option, the **cost-effectiveness ratio** `cpr = cooling_c / cost_per_cell` — degrees of cooling per rupee — and keeps the largest.

### The `heat_priority_boost`, and its two constants

```python
        heat_priority_boost = 1 + max(0, (row["predicted_temp"] - 35)) * 0.02
```

The intent: two cells might have identical cost-effectiveness on paper, but the hotter one has more headroom to improve, so nudge it up the list. The formula reads as:

- `row["predicted_temp"] - 35` — how many degrees above **35 °C** this cell is. The 35 is a threshold for "this is a hot cell worth prioritising"; it is not derived from any distribution in the data, it is a round number in the right neighbourhood for a heat-stress cut-off.
- `max(0, ...)` — clamps the excess at zero, so a cell *below* 35 °C is never *penalised*. Without this, a 25 °C cell would get a multiplier of `1 + (−10 × 0.02) = 0.8` and be pushed down the list for being cool. The clamp makes the adjustment a one-directional bonus.
- `× 0.02` — **2% uplift per degree above the threshold.** Deliberately tiny: a cell at 40 °C gets `1 + 5 × 0.02 = 1.10`, a 10% boost. That is small enough that it can only ever break ties or reorder near-equal options; it can never overturn the ~4.8× cost-effectiveness gap between `trees` and `cool_roof`. This is a tie-breaker wearing the clothes of a scoring term, and the comment's word *"slightly"* is accurate.
- `1 + ...` — makes it a multiplier centred on 1, so a cell at or below the threshold is scored exactly on its raw ratio.

**And on this dataset it never fires once.** The `predicted_temp` column is the satellite's LST, and across all 6,108 recommendable cells it ranges from **20.94 °C to 33.09 °C**, mean 27.27 °C. Not one cell reaches 35. So `max(0, temp − 35)` is 0 everywhere, `heat_priority_boost` is exactly 1 everywhere, and `adjusted_cpr` equals the raw `cpr` in every row of the committed output. The constants are defensible as intent; their effect on the current run is nil. Consequences for the ranking are in [the greedy ranking](#the-greedy-ranking) below, and they are not small.

One naming trap for whoever re-runs this on hotter data: the exported column named `cooling_per_rupee` holds `adjusted_cpr`, the boosted value — not the raw `cooling_c / cost_per_cell`. Today they are numerically identical because the boost is 1. The day the temperature column comes from the ML module, or the day the threshold is lowered, they diverge, and the column name will not warn you.

## What actually comes out: three consequences

All three are verified against the committed CSVs, not inferred from the code.

### 1. Only `trees` is ever recommended

All **6,108** rows of `recommendation.csv` carry the intervention `trees`. Not most — all of them. The arithmetic is a two-line proof:

```
trees:      0.8 °C ÷ ₹5,000  = 1.6e-4 °C per rupee
cool_roof:  1.0 °C ÷ ₹30,000 = 3.3e-5 °C per rupee
```

Trees beat cool roofs by **≈4.8×** on cost-effectiveness. And under the proxy, the two are legal on exactly the same reachable classes — `moderate` and `bare_or_built_hot` are in both `allowed_land_cover` lists — so wherever `cool_roof` is an option, `trees` is also an option and wins by a factor of nearly five. The `heat_priority_boost` cannot rescue it: at 2% per degree it would need a cell about 190 °C above the threshold to close a 4.8× gap.

`pocket_park` and `green_roof` never appear because their allowed lists are empty by design — that much was intentional and documented.

**`cool_roof` is different, and this part was nobody's intention.** It is not disabled: it is passed to `suitable_interventions_for_cell` for every recommendable cell and returned as a legal option every single time. It is *considered* 6,108 times and *selected* zero times. For it to win anywhere, there would have to be a cell where `cool_roof` is legal and `trees` is not — and comparing the two lists, exactly one class distinguishes them: **`building_dense`**, which appears in `cool_roof`'s list and not in `trees`'. That is a class the proxy classifier can never emit; it only ever returns `vegetated`, `moderate` or `bare_or_built_hot`. So `cool_roof` is dead code on the current data by accident, via a path that no comment in the file anticipates. See [`INTEGRATION_AUDIT.md`](../INTEGRATION_AUDIT.md) finding 5.

Net effect: **"four intervention types" in the pitch is one intervention type in the output.** Say so before a judge finds it.

### 2. Every excluded cell is excluded for being green

`excluded.csv` holds **2,036** rows, and the reason column has exactly one distinct value across all of them: `already vegetated - no action needed`. Those 2,036 cells are precisely the `vegetated` class — the top NDVI quartile — which appears in no intervention's `allowed_land_cover` list at all, so `suitable_interventions_for_cell` returns an empty list for every one of them.

6,108 recommended + 2,036 excluded = 8,144, the full grid. Nothing is lost.

### 3. `NEVER_TOUCH` excludes zero cells

The road/highway/water/wetland veto — the module's headline safety rule, and spec item 2 for the whole module — fires **zero times** on the current data. Not because the rule is wrong, but because *none of those four labels exists in the input*. The proxy classifier's entire vocabulary is `vegetated` / `moderate` / `bare_or_built_hot`; it cannot distinguish a road from bare soil, because from NDVI alone they look identical.

So the veto is logically correct and numerically inactive. A road in Guwahati is currently sitting in the `bare_or_built_hot` class being recommended for tree planting. This is a data gap, not a logic gap: the rule is written, would fire under the synthetic branch, and becomes live the moment a real land-cover column arrives — a one-flag change to `USE_PROXY_LANDCOVER`.

## The greedy ranking

```python
ranking = recommendation.sort_values("cooling_per_rupee", ascending=False).reset_index(drop=True)
ranking["rank"] = ranking.index + 1

if BUDGET_RUPEES is not None:
    ranking["cumulative_cost"] = ranking["cost_rupees"].cumsum()
    ranking["within_budget"] = ranking["cumulative_cost"] <= BUDGET_RUPEES
    n_selected = ranking["within_budget"].sum()
```

Four lines. Sort every recommendable cell descending by cost-effectiveness; number them from 1; run a **cumulative sum** of cost down the sorted list (`cumsum` gives, at each row, the total cost of that row and everything above it); mark a row as funded while that running total is still within budget.

**What "greedy" means here.** A greedy algorithm takes the best-looking option at each step and never revisits. This one takes the most cost-effective cell, then the next, and so on until the money runs out. It never asks whether skipping an expensive cell would let it afford two cheaper ones.

**Why this is deliberately not a knapsack optimiser.** The proper formulation of "maximise total cooling subject to a budget" is the 0/1 knapsack problem, solvable exactly by dynamic programming. The file states the choice outright:

```python
# This is intentionally NOT an optimizer (no knapsack DP, no RL/GA).
# Sort descending by cooling_per_rupee, walk down, stop at budget.
# Simple, explainable, defensible in a 5-hour hackathon.
```

**What that costs in optimality.** For the fractional version of the knapsack problem, a ratio sort is provably optimal. For the 0/1 version it is not, but the gap is bounded and it is largest when item costs are large relative to the budget — one expensive item can leave a big unusable remainder. Here every funded item costs ₹5,000 against a ₹5,000,000 budget: 1/1000th. The budget divides exactly, no remainder is stranded, and in this configuration the greedy solution is in fact the optimal one. The theoretical loss is zero on this data.

**Why explainability was judged worth more.** A stakeholder can be told the whole method in one sentence — *"we ranked every cell by cooling per rupee and funded down the list until the money ran out"* — and can then audit any individual row by hand. A dynamic-programming table cannot be checked by inspection, and the few percent it might recover on a harder instance is not worth the loss of that property when the *cost inputs themselves are placeholders*. Optimising precisely against numbers you have labelled as assumptions is false precision.

### The budget walk, and where it cuts

```
Rank 1000: +102059+29101  trees  ₹5,000  cumulative ₹5,000,000  within_budget True
Rank 1001: +102059+29102  trees  ₹5,000  cumulative ₹5,005,000  within_budget False
```

**1,000 of 6,108** cells are funded. The cut is exactly where the arithmetic puts it: 1,000 × ₹5,000 = ₹5,000,000, hitting the budget precisely, and cell 1,001 would be the first rupee over. The full 6,108-cell programme would cost **₹30,540,000** (the last row's `cumulative_cost`), so the budget covers about 16% of the recommendable city.

### The ranking is a complete tie — and what that means

Here is the part that the code's comments, this module's README, and the integration audit all miss, and it follows directly from the boost never firing.

Every one of the 6,108 recommendable cells gets `trees`, so every one gets `cpr = 1.6e-4`. Every one has `predicted_temp < 35`, so every one gets `heat_priority_boost = 1`. Therefore every one gets **the identical score**. Checked against the committed file: the `cooling_per_rupee` column of `ranking.csv` contains exactly **one distinct value, 0.00016**, across all 6,108 rows.

A sort key that is constant sorts nothing. Three consequences follow, and they are worth stating carefully:

- **`rank` carries no priority information.** Rank 1 is not more urgent, hotter, or better value than rank 6,108. They are indistinguishable to the scoring function.
- **The budget cut is arbitrary among equals.** Empirically, the `grid_id` column of `ranking.csv` is byte-identical to that of `recommendation.csv` — the committed output preserves input row order exactly. Since `grid_id` runs in a west-to-east scan order, the ₹50 lakh does not go to the 1,000 hottest or neediest cells; it goes to the 1,000 westernmost ones. That is a geography, not a priority.
- **Don't rely on that order holding.** `sort_values` defaults to `kind="quicksort"`, which is not a stable sort, so tie order is not guaranteed by pandas. What can be defended is the empirical statement above: all keys tie, and the committed output happens to preserve input order.

None of this is a coding error — every line does exactly what it says. It is a scoring model that has no discriminating power on the data it was pointed at, and it will stay that way until at least one of three things changes: real land cover arrives (giving cells different legal option sets, so different winners and different ratios), the temperature column comes from a model rather than raw LST, or the `35` threshold is lowered to somewhere inside the data's actual 20.94–33.09 °C range. Lowering the threshold to, say, 30 is the cheapest of the three and would immediately make the ranking mean something.

Until then: present the output as *"1,000 cells we can afford to plant"*, and not as *"the 1,000 highest-priority cells."*

## The cost-model conflict

Two modules in this project attach a rupee figure to the same word. They disagree by between 18× and 67×.

- **Decision-Support** (this module) uses flat per-cell placeholders: trees cost ₹5,000 per cell, full stop, regardless of the cell.
- **Machine Learning & Prediction** uses an area-based model in `COST_HEURISTICS`: an INR-per-m² rate × a coverage fraction × that cell's actual computed area.

```python
COST_HEURISTICS: dict[str, dict[str, float]] = {
    "Tree cover": {"inr_per_m2": 150.0, "coverage_fraction": 0.25},
    "Cool roof": {"inr_per_m2": 400.0, "coverage_fraction": 0.15},
    "Green park": {"inr_per_m2": 250.0, "coverage_fraction": 0.10},
    "None": {"inr_per_m2": 0.0, "coverage_fraction": 0.0},
}
```

The `coverage_fraction` is what makes that model physically motivated: you cannot plant trees over 100% of a cell that also contains houses and roads, so only a quarter of the area is treated. Multiplying by the cell's real area — about 8,917 m², computed from the polygon bounds rather than assumed — gives a cost that scales with the thing being paid for. The flat model has no such story; ₹5,000 is a number.

**The project's decision, and it is not a compromise:** the ML module's model is **authoritative for anything displayed, reported, quoted, or pitched.** Decision-Support's figures are retained for exactly one reason — its `cooling_per_rupee` ranking depends on the *ratios* between them, not their magnitudes, so replacing them would silently reorder the output. They are an internal scoring input, not a cost estimate.

**Never put the two side by side.** They are different units on different bases, and presenting both invites a reader to treat them as competing estimates of one quantity when they are not estimates of the same quantity at all. If you need the comparison for an audit, it already exists in exactly one place and should stay there: [`08-limitations.md`](./08-limitations.md#costs). Link to it; do not reproduce it.

Note that the ratio arithmetic used above to explain why `trees` always wins — 0.8/5,000 against 1.0/30,000 — is not affected by any of this. That is a comparison *within* one cost model, which is precisely the use the numbers are still valid for.

## The three output files

All three are written next to the script, and their resolved paths are printed at the end of the run so there is no guessing about where they went.

### `recommendation.csv` — 6,108 rows

Per-cell best option, for every cell that has one.

```python
recommendation_cols = ["grid_id", "lat", "lon", "land_cover", "predicted_temp",
                        "intervention", "cost_rupees", "cooling_c"]
```

| Column | Meaning |
|---|---|
| `grid_id` | The cell's identifier, e.g. `+102027+29090`, carried straight through from the source CSV |
| `lat`, `lon` | Centroid, from `extract_centroid` |
| `land_cover` | Proxy class — `moderate` (4,072 rows) or `bare_or_built_hot` (2,036 rows) |
| `predicted_temp` | LST in °C, despite the name |
| `intervention` | `trees` in all 6,108 rows |
| `cost_rupees` | `5000.0` in all rows |
| `cooling_c` | `0.8` in all rows |

### `ranking.csv` — 6,108 rows

The same cells, sorted, ranked, and marked funded or not.

```python
ranking_cols = ["rank", "grid_id", "lat", "lon", "intervention", "cost_rupees",
                 "cooling_c", "cooling_per_rupee", "cumulative_cost", "within_budget"]
```

Adds `rank` (1–6,108), `cooling_per_rupee` (`0.00016` in every row — see [the tie](#the-ranking-is-a-complete-tie--and-what-that-means)), `cumulative_cost` (₹5,000 to ₹30,540,000 in ₹5,000 steps) and `within_budget` (**1,000 `True`**, 5,108 `False`).

The export uses `columns=[c for c in ranking_cols if c in ranking.columns]` so that setting `BUDGET_RUPEES = None` — which skips the `cumulative_cost` computation entirely — degrades to a file without that column rather than raising a `KeyError`.

### `excluded.csv` — 2,036 rows

Cells with no valid intervention, recorded rather than silently dropped. The comment gives the reason: *"transparency matters for the demo."*

```python
excluded_cols = ["grid_id", "lat", "lon", "land_cover", "predicted_temp", "exclusion_reason"]
```

`land_cover` is `vegetated` in all 2,036 rows and `exclusion_reason` is `already vegetated - no action needed` in all 2,036 rows. Zero rows carry the never-touch reason.

A note on provenance: these three files were committed before the path fix described in [§2](#2-path-resolution--the-fix-that-made-this-module-runnable), during a period when the script could not run from a clone at all. What can be verified is that they are fully consistent with the real 8,144-row dataset and with the logic in the code as it stands today — 6,108 + 2,036 = 8,144, every intervention is `trees`, every score is 0.00016, exactly 1,000 rows are within budget, and the final cumulative cost is ₹30,540,000. (`INTEGRATION_AUDIT.md` quotes these as "6,108 / 6,109 / 2,037 rows" — its counts include the header line for two of the three files; the data-row counts are 6,108 / 6,108 / 2,036.) Every number on this page comes from those files or from the source dataset. Nothing here was produced by re-running the script.

## What to fix, in order

1. **Lower or remove the `35` in `heat_priority_boost`**, or wire in a temperature column that actually reaches it. Until then the ranking has no discriminating power and `rank` is decorative. Cheapest fix on this list by a wide margin.
2. **Re-run the Earth Engine export** with the corrected NDVI rescale and the land-cover join. This is the upstream fix that dissolves most of this page's caveats at once — it makes `USE_PROXY_LANDCOVER = False` possible, which re-enables `pocket_park` and `green_roof`, gives `cool_roof` a class it can win on, and makes `NEVER_TOUCH` numerically active for the first time. Blocked on Earth Engine account access; see [`08-limitations.md`](./08-limitations.md).
3. **Take `predicted_temp` from the ML module's predictions** rather than substituting raw LST, so the column name stops lying.
4. **Either wire up `min_cell_area_m2` or delete it** — and if you wire it up, fix `GRID_CELL_AREA_M2` to the real ~8,917 m² first.

Items 2 and 3 are single-flag changes in `load_data()` with no downstream rework. The module's own [`README.md`](../Decision-Support/README.md) doubles as its spec audit and covers the same ground from a compliance angle.

---

## Where to next

- [`06-frontend.md`](./06-frontend.md) — the dashboard that renders the pipeline's output. Not yet written; [`frontend/README.md`](../frontend/README.md) is the current source for how it consumes all of this.
- [`08-limitations.md`](./08-limitations.md) — the consolidated list of which numbers in this repo are measurements and which are assumptions. Read before quoting any figure from this page.
