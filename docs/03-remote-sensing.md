# 3. Remote Sensing & Data Engineering

This module is the head of the pipeline: it turns raw satellite imagery of Guwahati into a table of 8,144 grid cells, each carrying a temperature, a vegetation index, a built-up index, a land-cover class and a heat-risk score. It is one file — `Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js` — and that file does not run on your computer. It runs on Google's servers, inside a hosted service called Google Earth Engine, which you drive from a browser. This page walks that script line by line, defines every remote-sensing term it uses, works out the arithmetic behind every magic number in it, and then tells you exactly how to run it yourself. It assumes you can program and assumes you have never touched satellite data.

## Contents

- [What this module is, and what Earth Engine is](#what-this-module-is-and-what-earth-engine-is)
- [Vocabulary you need first](#vocabulary-you-need-first)
- [The study area](#the-study-area)
- [The script, section by section](#the-script-section-by-section)
  - [§1 Load the boundary](#1-load-guwahati-boundary)
  - [§2 Load Landsat 8](#2-load-landsat-8-data)
  - [§3 The QA_PIXEL cloud and shadow mask](#3-per-pixel-cloud-and-shadow-mask)
  - [§4 Median composite](#4-median-composite)
  - [§5 Land Surface Temperature](#5-land-surface-temperature-lst)
  - [§6 NDVI — and the bug this module is known for](#6-ndvi-calculation)
  - [§7 NDBI](#7-ndbi-calculation)
  - [§8 Land cover and vegetation](#8-land-cover-and-vegetation)
  - [§9 Normalisation](#9-normalize-lst-and-ndvi)
  - [§10 Heat Risk Index](#10-heat-risk-index)
  - [§11 Building the 100 m grid](#11-create-100m-grid)
  - [§12 Extracting features per cell](#12-extract-grid-wise-features)
  - [§13 Preview](#13-preview-dataset)
  - [§14–16 The four exports](#1416-the-four-exports)
  - [§17 Visualisation](#17-visualization)
- [How to actually run it](#how-to-actually-run-it)
- [What is still blocked, and which files are stale](#what-is-still-blocked-and-which-files-are-stale)
- [Where to next](#where-to-next)

---

## What this module is, and what Earth Engine is

**Google Earth Engine** is a hosted raster-processing service. Google keeps a copy of most of the world's public satellite archives — decades of Landsat, Sentinel, MODIS, plus derived products — on their own storage, next to a large compute cluster. You write a script in a browser IDE at [code.earthengine.google.com](https://code.earthengine.google.com/), press Run, and the script is shipped to Google's cluster, executed there against imagery that never leaves their datacentre, and only the results come back to you.

A **raster** is an image-shaped dataset: a rectangular grid of pixels, where each pixel holds one or more numbers. A satellite scene is a raster. A **band** is one of those numbers — one measurement layer within the image. Landsat 8 scenes carry bands named `SR_B1` … `SR_B7`, `ST_B10`, `QA_PIXEL` and others; each is a separate grid of numbers covering the same ground.

Two consequences follow, and they explain a lot about this module:

1. **There is nothing to install.** No `pip install`, no `requirements.txt`, no virtual environment. The only dependency is a Google account with Earth Engine access and a browser. Compare this with [`04-machine-learning.md`](./04-machine-learning.md), which is ordinary local Python and does have installs.
2. **The script is not reproducible by cloning the repo alone.** Running it needs an Earth Engine account, and the results are delivered to *the runner's* Google Drive — not into the repository. Somebody has to run it and then copy files back in by hand. That single fact is the root cause of the module's biggest open problem, described at the end of this page.

The language is JavaScript, but not browser JavaScript. Calls like `ee.ImageCollection(...)` do not compute anything locally; they build a description of a computation, which Earth Engine evaluates on the server when something forces it to — a `print`, a map layer, or an export. This is why every value you want to inspect goes through `print(...)` rather than being available as a plain JavaScript number.

Where this module sits in the whole project: see [`01-architecture.md`](./01-architecture.md).

## Vocabulary you need first

Every term the script depends on, in one sentence each. They are used freely after this table.

| Term | Meaning |
|---|---|
| **Digital number (DN)** | The raw integer stored in a pixel. It is not a physical quantity — it is a scaled, offset integer that you must convert before it means anything. Landsat stores DNs to keep files small and lossless. |
| **Surface reflectance** | The fraction of sunlight hitting the ground that bounces back, per wavelength band, with the atmosphere's effect mathematically removed. A physical quantity in the range 0–1 (roughly). Stored as a DN; you convert with a scale and an offset. |
| **Land surface temperature (LST)** | The temperature of the ground itself — asphalt, roof, grass — as measured by the satellite's thermal-infrared sensor. Different from air temperature, which is what a weather station reports. LST is what an urban-heat study wants, because it is the surface that stores and re-radiates heat. |
| **NDVI** | Normalized Difference Vegetation Index. A number from −1 to +1 that summarises how much living green vegetation is in a pixel. Higher means more vegetation. |
| **NDBI** | Normalized Difference Built-up Index. Same shape of formula, different bands, and high values indicate built-up impervious surfaces such as concrete and metal roofing. |
| **Cloud mask** | A per-pixel decision to discard pixels that are cloud, cloud shadow or haze, so that they do not pollute the computed statistics. |
| **Bitmask** | A single integer whose individual binary digits (bits) each carry an independent yes/no flag. You test one flag by bitwise-ANDing the integer with a number that has only that one bit set. |
| **Median composite** | Collapsing a stack of images taken at different times into one image, by taking the per-pixel median across the stack. |
| **Categorical vs continuous band** | A *continuous* band holds a measurement on a scale where arithmetic is meaningful (27.3 °C, NDVI 0.42). A *categorical* band holds a code standing for a class (10 = tree, 50 = built-up); averaging those codes is nonsense, because the halfway point between "tree" and "built-up" is not a thing. |
| **Reducer** | An Earth Engine object describing how to collapse many pixel values into fewer numbers — mean, median, min/max, mode, histogram. You pass a reducer to functions like `reduceRegion` to say *how* to summarise. |
| **Vectorisation** | Converting a raster (pixels) into vector geometry (polygons with coordinates). Used here in reverse of the usual purpose: not to trace real shapes, but to manufacture a grid. |
| **EPSG:4326** | A standard identifier for the coordinate system "plain longitude and latitude on the WGS 84 ellipsoid, in degrees." Its critical property here: it is *not* a metric system. One degree of longitude is a different number of metres at every latitude. |
| **`scale` (in Earth Engine)** | The ground resolution, in metres, at which a computation should be performed — `scale: 30` means "sample this on a 30 m grid." It is a request for a resolution, not a zoom level. |

---

## The study area

`Remote Sensing & Data Engineering/Boundary/guwahati_boundary.geojson` is a 6,840-byte GeoJSON file. Its structure, read directly from the file:

- Top-level keys: `type`, `name`, `crs`, `features`.
- `type` is `FeatureCollection`; `name` is `guwahati_boundary`.
- `crs` is `{"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}` — CRS84 is longitude/latitude in degrees on WGS 84, i.e. the same coordinate convention as EPSG:4326 but with the axis order written longitude-first, which is what GeoJSON requires.
- Exactly **one** feature, whose geometry is a `MultiPolygon` containing a single polygon with a single ring of **163 coordinate pairs**. So: one closed outline, no holes, no islands, 163 vertices.
- Coordinate extent: longitude 91.65192 to 91.83241, latitude 26.10118 to 26.20858.

Its `properties`:

| Property | Value |
|---|---|
| `shapeName` | `Guwahati` |
| `shapeISO` | *(empty)* |
| `shapeID` | `7132399B10647404007859` |
| `shapeGroup` | `IND` |
| `shapeType` | `ADM3` |

Those property names are the signature of **geoBoundaries**, an open database of administrative boundaries for every country. **ADM3** means administrative level 3: level 0 is the country, level 1 the state, level 2 the district, level 3 the sub-district or city-level unit. `shapeGroup: IND` is India. So this polygon is geoBoundaries' third-level unit named Guwahati.

Note the consequence, because it constrains every result downstream: an ADM3 polygon is *a* definition of Guwahati, not *the* definition. The area it encloses is roughly 81 km², smaller than the full municipal extent — see the structural caveats in [`08-limitations.md`](./08-limitations.md).

### The boundary is read as an asset, not from this file

This is the thing that stops newcomers. The script does **not** read `guwahati_boundary.geojson` from the repository. It cannot: the script runs on Google's servers, which have no access to your filesystem or to GitHub. Instead the boundary must first be uploaded into Earth Engine, where it becomes an **asset** — a dataset stored in your Earth Engine cloud project and addressed by a path. The script then refers to it by that path. See [§1](#1-load-guwahati-boundary) for the exact line and [How to actually run it](#how-to-actually-run-it) for the upload procedure.

---

## The script, section by section

The file opens with a comment block that is itself worth reading, because it is a changelog of the rewrite this page documents:

```js
// Spec-compliance revision:
//   - Landsat C2 L2 surface reflectance is now rescaled
//     (x 0.0000275, -0.2) before NDVI / NDBI. The -0.2
//     offset does not cancel in a normalized difference,
//     so the previous raw-DN NDVI was badly compressed.
```

Everything that comment claims is verified below.

### 1. Load Guwahati Boundary

```js
var guwahati = ee.FeatureCollection(
  "projects/urban-heat-guwahati/assets/guwahati_boundary"
);
```

*(lines 29–31 of the file.)*

A **`FeatureCollection`** in Earth Engine is a set of vector features — geometries with attached properties. Here it holds the single ADM3 polygon.

The string is an asset path, and it decomposes as `projects/` + `<cloud-project-name>` + `/assets/` + `<asset-name>`. `urban-heat-guwahati` is the original author's private Earth Engine cloud project. **You do not have access to it.** Nothing about this path is public, and there is no way to be granted access to it by cloning the repository. To run the script you upload your own copy of the GeoJSON and change this string. That is step 3 of [How to actually run it](#how-to-actually-run-it).

`guwahati` is used three ways in the rest of the script: as a spatial filter (`filterBounds`), as a clipping shape (`clip`), and as a region for statistics (`reduceRegion`, `Export`). It is the one object that ties everything to Guwahati specifically.

### 2. Load Landsat 8 Data

```js
var landsat = ee.ImageCollection(
  "LANDSAT/LC08/C02/T1_L2"
)
.filterBounds(guwahati)
.filterDate(
  '2025-01-01',
  '2025-12-31'
)
.filter(
  ee.Filter.lt('CLOUD_COVER',20)
);
```

**What the dataset ID means.** `LANDSAT/LC08/C02/T1_L2` is Earth Engine's identifier for **Landsat 8, Collection 2, Tier 1, Level 2**:

| Part | Meaning |
|---|---|
| `LC08` | Landsat 8, the satellite. Launched 2013, revisits any point roughly every 16 days, imaging at 30 m per pixel for the optical bands. |
| `C02` | **Collection 2** — the second full reprocessing of the entire Landsat archive by USGS, with improved geometric and radiometric calibration. Collection number matters because the scale/offset constants used in §5 and §6 are Collection-2-specific. |
| `T1` | **Tier 1** — the highest-quality subset, meeting strict geolocation-accuracy criteria. Tier 2 scenes exist but are less well registered. |
| `L2` | **Level 2** — atmospherically corrected products: *surface* reflectance and *surface* temperature, as opposed to Level 1's top-of-atmosphere values. Level 2 is what you want when you care about the ground rather than the atmosphere. |

An **`ImageCollection`** is a lazily-evaluated set of images — here, every Landsat 8 Tier 1 Level 2 scene ever taken, before filtering. The three filters cut it down:

- **`filterBounds(guwahati)`** — keep only scenes whose footprint intersects the boundary polygon. Landsat scenes are roughly 185 km × 180 km tiles on a fixed path/row grid, so this typically leaves a handful of overlapping tiles.
- **`filterDate('2025-01-01', '2025-12-31')`** — keep only scenes captured in that window. **Why a whole year?** Landsat's 16-day revisit gives at most ~23 opportunities per year per path, and Guwahati sits in a monsoon climate where a large fraction of those are wholly clouded. Narrowing to a season would risk ending up with two or three usable scenes, and the median in §4 needs a stack deep enough that a per-pixel median is a stable statistic rather than a coin flip. The cost of the choice is that the output is an *annual* median — there is no seasonal or diurnal dimension in this dataset at all, which is listed as a structural caveat in [`08-limitations.md`](./08-limitations.md).
- **`ee.Filter.lt('CLOUD_COVER', 20)`** — keep only scenes whose `CLOUD_COVER` metadata property is less than 20. `CLOUD_COVER` is a **scene-level** number: the percentage of the whole tile that USGS's cloud algorithm judged clouded. **Why 20?** It is a trade-off dial. Set it to 5 and you get very clean scenes but very few of them, possibly too few for a meaningful median. Set it to 80 and you get plenty of scenes, most of them mostly cloud. 20 is a conventional middle setting: it discards scenes that are hopeless while keeping the stack deep. Nothing physical fixes it at 20 — it is a judgement.

The crucial limitation of this filter is that it is all-or-nothing per scene. A scene at 19% cloud passes the filter **whole**, clouded pixels included. That is precisely what §3 exists to fix.

```js
print(
  "Number of Landsat Images:",
  landsat.size()
);
```

`print` writes to the Console panel on the right of the Code Editor. This one tells you how many scenes survived the filters — the first thing to check after a run, because if it prints 0 or 1 the rest of the output is meaningless.

### 3. Per-Pixel Cloud and Shadow Mask

This is the densest part of the script, and worth the most careful reading. The script's own comment states the motivation:

```js
// Scene-level CLOUD_COVER above still admits whole scenes
// at up to 20% cloud. This drops the clouded pixels too.
```

```js
function maskL8(img) {
  var qa = img.select('QA_PIXEL');
  var mask = qa.bitwiseAnd(1 << 1).eq(0)   // dilated cloud
    .and(qa.bitwiseAnd(1 << 2).eq(0))      // cirrus
    .and(qa.bitwiseAnd(1 << 3).eq(0))      // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));     // cloud shadow
  return img.updateMask(mask);
}
```

#### What a bitmask is and why quality flags are packed into one

Every Landsat scene carries a band called `QA_PIXEL` — a quality-assessment band. For every pixel it answers a list of independent yes/no questions: is this fill (no data)? is it cloud? is it cloud shadow? is it cirrus? is it snow? is it water?

You could store one band per question. Nobody does, because storing sixteen separate 1-bit layers wastes space and I/O when you can pack all sixteen into the bits of one 16-bit integer. That packed integer is a **bitmask**: bit position *n* of the integer holds the answer to question *n*, where 1 conventionally means "yes, this condition applies."

Reading back one flag means isolating one bit. That is what `bitwiseAnd` does. `1 << n` is the integer with a single 1 in position *n* — `1 << 0` = 1, `1 << 1` = 2, `1 << 2` = 4, `1 << 3` = 8, `1 << 4` = 16. Bitwise-AND keeps only bits set in *both* operands, so `qa & (1 << 3)` is non-zero exactly when bit 3 of `qa` is 1, and zero otherwise. Testing `.eq(0)` therefore asks: **"is this condition absent?"**

#### Walked digit by digit

Take a concrete QA_PIXEL value. Suppose a pixel has `QA_PIXEL = 22280`. In 16-bit binary, most-significant bit first:

```
bit:    15 14 13 12 11 10  9  8   7  6  5  4  3  2  1  0
value:   0  1  0  1  0  1  1  0   1  0  0  0  1  0  0  0
```

Now run the four tests. `1 << 3` is 8, which in binary is `0000 0000 0000 1000` — a single 1 in position 3.

```
qa        0101 0110 1000 1000
1 << 3    0000 0000 0000 1000
AND       0000 0000 0000 1000   = 8
```

8 is not 0, so `.eq(0)` yields **false** for this pixel: bit 3 is set, the pixel is flagged cloud, and it fails the test.

Contrast with bit 2 (`1 << 2` = 4, binary `...0100`):

```
qa        0101 0110 1000 1000
1 << 2    0000 0000 0000 0100
AND       0000 0000 0000 0000   = 0
```

Zero, so `.eq(0)` yields **true**: bit 2 is clear, this pixel is not flagged cirrus.

The four tests are combined with `.and(...)`, so `mask` is 1 only where **all four** conditions are absent. Since bit 3 failed, this pixel's mask value is 0 regardless of the others, and it is discarded.

Note that this is happening per pixel across an entire image at once — `qa` is an `ee.Image`, and `bitwiseAnd`, `eq` and `and` are image-wide operations that produce new images. There is no loop anywhere.

#### Why bits 1, 2, 3, 4

Each corresponds to one way a pixel can be optically unusable, per the script's inline comments:

| Bit | Flag | Why it must be excluded |
|---|---|---|
| 1 | Dilated cloud | A buffer zone grown outward from detected cloud. Cloud edges are fuzzy and the detector is imperfect, so the pixels just outside a confirmed cloud are contaminated by partial cover and scattered light. Dropping the buffer is a deliberately conservative choice. |
| 2 | Cirrus | High, thin ice cloud. It often looks unremarkable in visible bands but attenuates and scatters the signal, so it corrupts reflectance and thermal readings without looking obviously wrong. |
| 3 | Cloud | Opaque cloud. The sensor is measuring the top of a cloud, not the ground. Both LST and reflectance are meaningless here. |
| 4 | Cloud shadow | Ground *is* visible, but it is lit only by diffuse skylight. Reflectance is depressed and surface temperature reads cool. Shadows are especially damaging because, unlike cloud, they look like plausible data. |

Bit 0 (fill) is not tested here; fill pixels are outside the imaged swath and are generally already masked in the delivered product. Bits above 4 (snow, clear, water and confidence pairs) are not conditions that make a pixel unusable for this analysis.

`img.updateMask(mask)` returns the image with masked-out pixels marked invalid. Masked pixels are not zeroed — they are *absent*, and Earth Engine's reducers skip them entirely. That distinction is what makes §4 work.

### 4. Median Composite

```js
var image = landsat.map(maskL8).median();
```

Two operations on one line.

`landsat.map(maskL8)` applies `maskL8` to every scene in the collection, producing a new collection of cloud-masked scenes. `.map()` here is Earth Engine's server-side map over an `ImageCollection`, not `Array.prototype.map`.

`.median()` then reduces that stack of images to one image, taking the per-pixel median across whichever scenes have a valid (unmasked) value at that pixel.

**Why the median and not the mean?** Because the median is robust to outliers and the mean is not. Consider one pixel over a year, with ten valid observations of a rooftop:

| Observation | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Reading | typical | typical | typical | **cloud-brightened** | typical | typical | typical | typical | **cloud-brightened** | typical |

A mean pulls toward those two contaminated readings in proportion to how extreme they are — one very bright cloud sliver can shift the annual mean noticeably. A median ignores magnitude entirely and asks only for rank: with 8 of 10 observations being genuine ground, the middle value is a genuine ground value no matter how extreme the other two are. Cloud is the archetypal outlier — bright in the optical bands, cold in the thermal band — so the median is the natural choice.

**How this composes with §3.** The two mechanisms catch different things. The `QA_PIXEL` mask removes pixels the USGS detector *recognised* as cloud. The median removes the residue — thin haze, undetected cloud edges, transient anomalies — that the detector missed, provided such contamination affects a minority of a pixel's observations. Masking first also makes the median better: it shrinks the stack to genuine ground observations, so the median is drawn from a cleaner population.

The output `image` is a single composite carrying all the Landsat bands, and it is the input to §5, §6 and §7.

### 5. Land Surface Temperature (LST)

```js
var lst = image
.select('ST_B10')
.multiply(0.00341802)
.add(149.0)
.subtract(273.15)
.rename('LST');
```

`ST_B10` is Landsat 8's Collection 2 Level 2 **surface temperature** band, derived from thermal-infrared band 10. Like every Level 2 band it is stored as a scaled integer digital number, not as a temperature. Converting takes three steps, each of which is one of the chained calls:

| Constant | What it is | Where it comes from |
|---|---|---|
| `0.00341802` | Multiplicative scale factor | Published by USGS for the Collection 2 Level 2 surface-temperature product. It is the step size, in kelvin, of one DN unit. Fixed by how the product was quantised — not a tunable parameter. |
| `149.0` | Additive offset, in kelvin | Also from the USGS product definition. Together with the scale it maps the integer range onto the temperature range the product covers. |
| `273.15` | Kelvin-to-Celsius conversion | 0 K is absolute zero; 273.15 K is 0 °C. Subtracting it converts an absolute temperature to Celsius. |

#### Worked example

Take a representative digital number — `ST_B10 = 44300` (a plausible value for this scene, chosen to illustrate, not read from any file):

```
step 1   44300 × 0.00341802  =  151.418
step 2   151.418 + 149.0     =  300.418   kelvin
step 3   300.418 − 273.15    =   27.27    °C
```

27.27 °C for an annual median in Guwahati is entirely believable, which is the sanity check you want.

**What would go wrong if the constants were different?** Getting the scale wrong stretches or squashes the whole temperature field: use a scale ten times too large and a 10 °C spread across the city becomes a 100 °C spread. Getting the offset wrong shifts every temperature by a constant: omit `+149.0` and DN 44300 becomes 151.4 K, i.e. −121.7 °C, which is obviously impossible and would be caught immediately. Omitting `−273.15` leaves you with kelvin — 300.4 instead of 27.3 — which downstream code and the `unitScale(20,34)` in §9 would quietly mangle rather than reject. Note that the two Landsat constants are *product* constants: if you switched to Collection 1, or to a Level 1 product, they would be wrong and would need replacing.

```js
var lst_guwahati = lst.clip(guwahati);
```

`clip` restricts the image to the boundary polygon. Everything outside becomes masked. This matters for the statistics that follow and for the GeoTIFF export in §16.

```js
print(
  "LST Statistics",
  lst_guwahati.reduceRegion({
    reducer: ee.Reducer.minMax(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);
```

`reduceRegion` collapses all pixels inside a geometry into summary numbers using a reducer. `ee.Reducer.minMax()` returns the minimum and maximum. The two constants:

- **`scale: 30`** — sample at 30 m, which is Landsat 8's native optical resolution. Asking for a finer scale would make Earth Engine resample without adding information; asking for a coarser one would throw away detail. 30 is the honest number for this sensor.
- **`maxPixels: 1e9`** — a safety limit. `reduceRegion` refuses to run rather than silently truncating if the region would require more than this many pixels, which protects you from accidentally requesting a continent-sized computation. **Is it binding here?** No, and it is worth seeing why: the polygon is about 81 km² = 81,000,000 m²; at 30 m resolution each pixel covers 900 m²; so the region is roughly 81,000,000 / 900 ≈ **90,000 pixels**, about four orders of magnitude below the 10⁹ limit. The constant is a guardrail with enormous headroom, not a tuned value. Set it far too low — say 1e4 — and these `print` calls would error out; raising it does nothing until your region gets very much bigger.

This same `reduceRegion` pattern with the same two constants recurs in §6, §7, §8 and §10.

### 6. NDVI Calculation

The most important section in the file, and the one whose earlier version is responsible for the project's largest known data problem.

```js
// Landsat C2 L2 surface reflectance -> physical reflectance
var sr = image
.select([
  'SR_B4',
  'SR_B5',
  'SR_B6'
])
.multiply(0.0000275)
.add(-0.2);
```

Three bands are pulled out and rescaled together:

| Band | Wavelength region | Used for |
|---|---|---|
| `SR_B4` | Red visible light | NDVI (as the RED term) |
| `SR_B5` | Near-infrared (NIR) — just beyond the red end of human vision | NDVI (as the NIR term), NDBI |
| `SR_B6` | Shortwave infrared 1 (SWIR1) — a longer infrared band | NDBI (§7) |

`0.0000275` and `-0.2` are the USGS Collection 2 Level 2 **surface reflectance** scale and offset — the direct analogue of §5's thermal pair, but for the optical bands. Applying them converts an integer DN into a physical reflectance, a fraction of incident light.

Check the arithmetic gives sane physics: a DN of 10000 becomes `10000 × 0.0000275 − 0.2 = 0.275 − 0.2 = 0.075`, i.e. 7.5% reflectance — dark, plausible for vegetation in red light. A DN of 20000 becomes `0.550 − 0.2 = 0.350`, i.e. 35% — bright, plausible for vegetation in near-infrared.

#### What a normalized difference is, and why NIR minus red measures vegetation

```js
var ndvi = sr
.normalizedDifference([
  'SR_B5',
  'SR_B4'
])
.rename('NDVI');
```

`normalizedDifference([a, b])` computes, per pixel:

```
(a − b) / (a + b)
```

With `a = SR_B5` (near-infrared) and `b = SR_B4` (red), that is the standard NDVI. Dividing by the sum is what makes it *normalized*: it bounds the result to [−1, +1] and cancels out overall brightness, so a shaded lawn and a sunlit lawn give similar NDVI even though their absolute reflectances differ.

The physical reason it works is a property of leaves. Chlorophyll absorbs red light hard — that is what photosynthesis is doing — so healthy vegetation reflects very little red. Meanwhile the internal cell structure of a leaf scatters near-infrared strongly, so vegetation reflects a lot of NIR. Vegetation therefore has NIR far above red, and NDVI near +1. Concrete, asphalt and bare soil reflect red and NIR at roughly similar levels, giving NDVI near 0. Water absorbs NIR more strongly than red, giving negative NDVI. So one number separates green from grey from wet.

#### The bug: the multiplier cancels, the offset does not

The pre-fix version of this section (**old code, shown only for contrast**) was:

```js
// PRE-FIX — this is NOT what the file contains now
var ndvi = image.normalizedDifference(['SR_B5','SR_B4']).rename('NDVI');
```

It ran the normalized difference straight on the raw digital numbers, with no rescale. Here is exactly why that matters.

Write the true reflectances as `mA + c` and `mB + c`, where `A` and `B` are the raw DNs, `m = 0.0000275` and `c = −0.2`. Substitute into the formula:

```
(mA + c) − (mB + c)          m(A − B)
─────────────────────  =  ──────────────────
(mA + c) + (mB + c)        m(A + B) + 2c
```

In the **numerator**, `c` subtracts away and `m` factors out. In the **denominator**, `m` factors out but `2c` remains, stranded. So the multiplier cancels completely — it genuinely does not matter — while the offset survives as an extra term in the denominator and shifts the whole result. And because `c` is *negative*, `2c` makes the denominator smaller, which makes the correct NDVI **larger** than the raw-DN version.

Worked with real digits, `SR_B5 = 20000` and `SR_B4 = 10000`:

| Computation | NIR term | RED term | Numerator | Denominator | NDVI |
|---|---|---|---|---|---|
| Raw DN (pre-fix code) | 20000 | 10000 | 10000 | 30000 | **0.3333** |
| Multiplier only, `× 0.0000275`, no offset | 0.5500 | 0.2750 | 0.2750 | 0.8250 | **0.3333** |
| Correct, `× 0.0000275 − 0.2` (current code) | 0.3500 | 0.0750 | 0.2750 | 0.4250 | **0.6471** |

Row 2 is the proof that the multiplier alone changes nothing: it is identical to row 1 to every digit. Row 3 is the whole difference, and it comes entirely from `0.8250 − 0.4000 = 0.4250` in the denominator.

The distortion is not a constant shift, either — the size of the error depends on the raw brightness, so you cannot correct the committed data after the fact by rescaling the NDVI column. The pixels have to be reprocessed.

#### The measured evidence

The [SPEC_AUDIT](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md) computed the NDVI distribution across all 8,144 rows of the committed dataset, which was exported by the pre-fix code:

```
NDVI   min −0.097   median 0.179   p95 0.295   p99 0.331   max 0.386
```

A maximum of **0.386** across an entire city with substantial tree cover and forested hills is not physically credible. Healthy dense vegetation reaches **0.7–0.85**. The observed ceiling is roughly half where the greenest pixel in the city should be — consistent with the sign of the algebra above, and diagnostic of exactly this bug. Every NDVI value in the committed data is compressed toward zero.

The full list of what that contaminates — `Heat_Risk`, the priority tiers, the vegetation split, both proxy land-cover classifiers, the regression, the dashboard — is in [`08-limitations.md`](./08-limitations.md) and is not repeated here.

```js
var ndvi_guwahati = ndvi.clip(guwahati);
```

Then the same `reduceRegion` / `minMax` print as in §5. After a re-run, **this is the print to check first**: if the maximum NDVI comes back around 0.8 rather than around 0.39, the fix has taken effect.

### 7. NDBI Calculation

```js
var ndbi = sr
.normalizedDifference([
  'SR_B6',
  'SR_B5'
])
.rename('NDBI');


var ndbi_guwahati = ndbi.clip(guwahati);
```

Identical machinery, different bands: SWIR1 minus NIR over their sum. Note it consumes the same rescaled `sr` image from §6, so it gets the offset correction for free — which matters, because the same offset algebra applies here.

Why these bands indicate built-up surfaces: vegetation is bright in NIR and comparatively dark in SWIR1 (partly because leaf water absorbs shortwave infrared), so vegetation gives negative NDBI. Concrete, metal roofing and asphalt reflect SWIR1 more than NIR, giving positive NDBI. NDBI therefore tends to run opposite to NDVI, and it is a useful independent signal for "how built-up is this cell" that does not simply restate NDVI — the two disagree on bare soil, which is low in both.

NDBI was marked *optional* in the module spec and was absent from the pre-fix script. It is computed now and, like the other new columns, is **absent from the committed dataset** because that dataset predates the rewrite.

### 8. Land Cover and Vegetation

```js
var worldcover = ee.ImageCollection('ESA/WorldCover/v200')
.first()
.select('Map')
.rename('LandCover')
.clip(guwahati);
```

**ESA WorldCover** is a global land-cover map produced by the European Space Agency from Sentinel-1 and Sentinel-2 imagery, at 10 m resolution. Every pixel on Earth is assigned to one class — tree cover, shrubland, grassland, cropland, built-up, bare, water and so on — encoded as a small integer. `v200` is version 2 of the product.

It is an *independent* source of truth about land use, not derived from the Landsat composite at all, which is exactly why it is valuable: it lets a cell be labelled "built-up" or "tree cover" without inferring that from NDVI, which is the thing currently known to be wrong.

The chain: `ee.ImageCollection(...)` — WorldCover is published as a collection even though there is effectively one global mosaic per version — then `.first()` takes that single image, `.select('Map')` picks the class band (`Map` is its band name), `.rename('LandCover')` gives it the name that will become the CSV column, and `.clip(guwahati)` restricts it to the study area.

```js
// binary vegetation: WorldCover classes 10 (tree), 20 (shrub),
// 30 (grass), 40 (crop)
var vegetation = worldcover
.remap(
  [10,20,30,40],
  [1,1,1,1],
  0
)
.rename('Vegetation');
```

**`remap(from, to, defaultValue)`** is a lookup-table operation on pixel values: wherever a pixel equals `from[i]`, replace it with `to[i]`; anything not in the `from` list becomes `defaultValue`. Here the four vegetated classes named in the comment — 10 tree, 20 shrub, 30 grass, 40 crop — all map to `1`, and *every other class* (built-up, bare, water and the rest) falls through to the default `0`.

The result is a **binary band**: 1 where vegetated, 0 where not. Its usefulness appears in §12, where taking the *mean* of a 0/1 band over a cell gives the **fraction** of that cell that is vegetated — a genuinely different measurement from NDVI, which measures how vigorous the vegetation is rather than how much of the cell it covers.

```js
print(
  "Land Cover Statistics",
  worldcover.reduceRegion({
    reducer: ee.Reducer.frequencyHistogram(),
    geometry: guwahati,
    scale:30,
    maxPixels:1e9
  })
);
```

`ee.Reducer.frequencyHistogram()` counts how many pixels fall into each distinct value — the right summary for a categorical band, and the wrong question to ask with `minMax`, which would only tell you the numerically smallest and largest class *codes*, a meaningless pair. This print tells you the class composition of Guwahati.

Note `scale: 30` even though WorldCover is natively 10 m: the whole pipeline works on Landsat's 30 m grid, so sampling WorldCover at 30 m keeps everything on one footing.

The `Vegetation` print that follows uses `minMax` — appropriate here, because the vegetation band is genuinely numeric (0 or 1), and the print is really a sanity check that the remap produced only those two values.

### 9. Normalize LST and NDVI

```js
// These bounds are now meaningful: with the surface
// reflectance rescale in section 6 the NDVI actually spans
// roughly -0.1 to 0.85, so unitScale(-0.2,0.8) is the right
// range rather than an over-wide one.

var lst_norm = lst_guwahati
.unitScale(20,34);


var ndvi_norm = ndvi_guwahati
.unitScale(-0.2,0.8);
```

`unitScale(min, max)` performs the linear rescale `(x − min) / (max − min)`, mapping the interval `[min, max]` onto `[0, 1]`. Its purpose here is to put temperature in °C and a dimensionless index onto the same footing so that §10 can subtract one from the other. Subtracting NDVI (range ~1.0 wide) from LST in °C (range ~13 wide) directly would let temperature dominate by an order of magnitude for no principled reason.

**`unitScale(20, 34)` for LST.** The committed dataset's LST runs 20.94 – 33.09 °C, median 27.29, so `[20, 34]` brackets the observed range with a small margin at each end. Worked: an LST of 27.0 °C maps to `(27.0 − 20) / (34 − 20) = 7/14 = 0.500`; an LST of 31.0 maps to `11/14 = 0.786`. Two caveats. First, those bounds were chosen against **pre-fix** data — the LST *arithmetic* in §5 is untouched by the rewrite, but the new §3 cloud mask changes which pixels enter the median, so the post-re-run LST range may shift and the bounds are worth re-checking. Second, because the bounds are absolute, they are city-specific: reuse this script on a hotter city and everything saturates at 1.0.

**`unitScale(-0.2, 0.8)` for NDVI.** The script's comment predicts a post-fix NDVI span of roughly −0.1 to 0.85 — note that this is a *prediction stated in a comment*, not a measurement; the only NDVI numbers anyone has measured on this dataset are the pre-fix ones in §6. Taking the comment at face value there is a visible mismatch: **0.85 exceeds the upper bound of 0.8.** By the arithmetic alone, a pixel at NDVI 0.85 gives `(0.85 − (−0.2)) / (0.8 − (−0.2)) = 1.05 / 1.0 = 1.05`, i.e. above 1. Whether Earth Engine clamps `unitScale` output to [0, 1] or lets it run past is not something this repository establishes, and it is not documented in any file here, so this page does not assert either behaviour — but the mismatch is real and should be resolved by re-checking the bounds against the actual measured range after a re-run.

Note also what the *old* bounds problem was: against pre-fix NDVI, which topped out at 0.386, `unitScale(-0.2, 0.8)` compressed the entire city into roughly the lower half of [0, 1]. The bounds were not wrong so much as matched to data that was wrong.

### 10. Heat Risk Index

```js
var heat_risk = lst_norm
.subtract(ndvi_norm)
.rename('Heat_Risk');
```

The whole index, in one subtraction: normalised temperature minus normalised vegetation. Hot and bare scores high; cool and green scores low. It is a deliberately simple, transparent construct rather than a fitted model — there is no ground truth for "heat risk" anywhere in this project against which a model could be fitted, a point made at more length in [`01-architecture.md`](./01-architecture.md).

Both operands nominally live in [0, 1], so the difference nominally lives in [−1, +1]. It is not a physical unit and should not be reported as one; it is a ranking score.

Because it is built from NDVI, it inherits the NDVI bug directly: under-credited vegetation means `Heat_Risk` is biased **high** everywhere in the committed data.

### 11. Create 100m Grid

```js
var grid = ee.Image.random()
.multiply(100000)
.toInt()
.reduceToVectors({

  geometry: guwahati.geometry(),

  scale:100,

  geometryType:'polygon',

  eightConnected:false,

  labelProperty:'grid_id',

  reducer:ee.Reducer.countEvery()

});
```

This is a trick, and it deserves unpacking because nothing about it is obvious.

The goal is a regular grid of ~100 m cells covering the boundary. Earth Engine has no single "make me a grid" call, but it does have `reduceToVectors`, whose actual purpose is **vectorisation**: converting a raster into polygons by grouping *contiguous pixels that share the same value* into one polygon each. Vectorise a land-cover map and you get one polygon per contiguous patch of forest, one per contiguous patch of city.

The trick inverts that. If you vectorise an image in which **no two neighbouring pixels ever share a value**, then no merging can occur, and `reduceToVectors` is forced to emit exactly one polygon per pixel — which is a grid.

How the image achieves that:

- **`ee.Image.random()`** produces a pseudo-random value in [0, 1) for every pixel.
- **`.multiply(100000)`** spreads that across a range of 100,000.
- **`.toInt()`** truncates to an integer. The result is a field of integers drawn from ~100,000 distinct values, so the chance that two adjacent pixels happen to land on the same integer is on the order of 1 in 100,000 — negligible across a few thousand cells.

The audit confirms the trick worked on the actual export: **every one of the 8,144 cells has `count = 1`**, meaning no cell absorbed more than one pixel. (Whether `ee.Image.random()` reproduces the identical field on a future run — and therefore whether a re-run yields the same cell boundaries — is not established by anything in this repository, so treat cell identity across runs as unverified.)

The parameters:

| Parameter | Effect |
|---|---|
| `geometry: guwahati.geometry()` | Vectorise only inside the boundary polygon. `.geometry()` pulls the raw geometry out of the `FeatureCollection`. |
| `scale: 100` | Do the vectorisation on a 100 m pixel grid. **This is what sets the cell size** — the only place "100 m" enters the script. |
| `geometryType: 'polygon'` | Emit filled polygons rather than centroids or bounding boxes. |
| `eightConnected: false` | Treat only the four edge-sharing neighbours as adjacent, not the eight including diagonals. With near-unique values nothing merges either way, but 4-connectivity is the conservative setting. |
| `labelProperty: 'grid_id'` | Name the property that carries the source pixel value. (§11's `map` immediately overwrites it — see below.) |
| `reducer: ee.Reducer.countEvery()` | Attach a `count` property to each polygon: how many source pixels it contains. This is the diagnostic that proved every cell is exactly one pixel, and it survives into the CSV as the `count` column. |

```js
var guwahati_grid = grid.map(function(feature){

  return feature.set({

    'grid_id':feature.id()

  });

});
```

This replaces `grid_id` — which at this point holds the meaningless random integer — with the feature's own Earth Engine ID. In the committed CSV, `grid_id` matches `system:index` and looks like `+102027+29089`; it *appears* to encode a pixel coordinate pair, though the repository does not document the format.

#### Why the cells are not square in metres

The grid is built in **EPSG:4326**, i.e. in degrees of longitude and latitude, so each cell is a fixed-size square *in degrees*. Measuring two adjacent cell corners in the committed CSV:

```
91.65331180814654 − 91.65241349286242 = 0.00089832°
```

Uniform, and the same in both axes. A degree-square is not a metre-square, because a degree of longitude shrinks as you move away from the equator, by a factor of cos(latitude). Guwahati sits at about 26.13° N:

```
east–west   0.00089832° × 111,320 m/° × cos(26.13°)
          = 0.00089832 × 111,320 × 0.8979
          = 89.78 m

north–south (measured on the exported geometries)
          = 99.3 m
```

So cells are **89.8 m × 99.3 m**, not 100 × 100. The north–south figure barely changes with latitude because a degree of latitude is nearly constant; the east–west figure is the one that shrinks, and 0.8979 is exactly the cos(26.13°) factor. (Computing north–south from a simple spherical constant gives 100.0 m and from an ellipsoidal meridian formula 99.5 m; the 99.3 m quoted here is the audit's figure measured from the exported polygons, and the small discrepancy is sphere-versus-ellipsoid, not an error in the grid.)

This is not a bug, but it must be stated whenever the grid is described. Per-cell areas are computed from the real polygon bounds downstream, so costs and densities are right — but "100 m squares" is a loose description. To get true 100 m squares you would build the grid in a metric projected coordinate system, e.g. UTM zone 46N (`EPSG:32646`), rather than in degrees.

```js
print(
  "Number of Grid Cells:",
  guwahati_grid.size()
);
```

The committed run printed 8,144.

### 12. Extract Grid-wise Features

The section that turns rasters into a table. It maps over every grid cell and runs one `reduceRegion` per band inside that cell's geometry.

The pattern, shown for LST:

```js
  var lst_value = lst_guwahati.reduceRegion({

    reducer:ee.Reducer.mean(),

    geometry:cell.geometry(),

    scale:30,

    maxPixels:1e9

  }).get('LST');
```

`reduceRegion` over the cell's own polygon, with `ee.Reducer.mean()`, at Landsat's native 30 m. Since a cell is ~90 × 99 m, roughly 9–12 Landsat pixels fall inside it, and their mean becomes the cell's LST. `.get('LST')` extracts the named result out of the returned dictionary — the key matches the band name set by `rename` back in §5.

The same shape repeats for `ndvi_value` (`.get('NDVI')`), `ndbi_value` (`.get('NDBI')`) and `heat_value` (`.get('Heat_Risk')`). Two of the six are deliberately different, and the script comments say why:

```js
  // categorical band - the modal class, not a mean
  var landcover_value = worldcover.reduceRegion({

    reducer:ee.Reducer.mode(),
```

**`Reducer.mode()` for land cover, not `mean()`.** WorldCover's values are class *codes*, not quantities. If a cell contains 6 pixels of class 10 (tree) and 4 of class 50 (built-up), the mean is 26 — a code that means nothing, and which is not even one of the classes present. The **mode**, the most frequently occurring value, returns 10: the dominant land-cover class of the cell, which is a true and useful statement. This is the categorical-versus-continuous distinction from the vocabulary table, made operational.

```js
  // mean of a 0/1 band = vegetated fraction of the cell
  var vegetation_value = vegetation.reduceRegion({

    reducer:ee.Reducer.mean(),
```

**`Reducer.mean()` for vegetation, and here the mean is exactly right** — precisely because §8 remapped the band to 0/1. The mean of a set of zeros and ones is the proportion of ones, so this yields the *vegetated fraction* of the cell: 0.0 fully unvegetated, 0.5 half, 1.0 fully. Same reducer as LST, entirely different meaning, because the band was constructed to make it so.

```js
  var c = cell.geometry().centroid(1).coordinates();
```

`centroid(1)` computes the cell's geometric centre; the `1` is a maximum-error tolerance in metres, telling Earth Engine that a 1 m approximation is acceptable — geodesic centroid computation is iterative and this bounds the work. `.coordinates()` returns the result as a `[longitude, latitude]` list, which is GeoJSON's axis order — longitude first. Hence:

```js
    'Longitude':c.get(0),

    'Latitude':c.get(1),
```

Index 0 is longitude, index 1 is latitude. Getting these the wrong way round is a classic error, and here it would place Guwahati (26° N, 91° E) somewhere in the Indian Ocean.

The full set written onto each cell:

```js
  return cell.set({

    'Longitude':c.get(0),

    'Latitude':c.get(1),

    'LST':lst_value,

    'NDVI':ndvi_value,

    'NDBI':ndbi_value,

    'LandCover':landcover_value,

    'Vegetation':vegetation_value,

    'Heat_Risk':heat_value

  });
```

Eight properties per cell. Column-level detail on what downstream code expects from these is in [`07-data-contracts.md`](./07-data-contracts.md).

**A note on cost.** This runs six `reduceRegion` calls per cell across 8,144 cells — roughly 49,000 region reductions. Earth Engine parallelises them, but this is the expensive part of the script and the reason the CSV and GeoJSON export tasks are not fast.

### 13. Preview Dataset

```js
print(
  "Sample Grid Dataset",
  grid_dataset.limit(5)
);
```

Prints the first five features to the Console. `limit(5)` is essential rather than cosmetic: printing all 8,144 would attempt to compute and serialise the entire dataset into the browser panel, which the Code Editor will refuse or choke on. This is the check to read before starting an export — if the five sample rows have the right columns and plausible values, the export is worth waiting for.

### 14–16. The four exports

```js
Export.table.toDrive({

  collection:grid_dataset,

  description:'dataset',

  fileFormat:'CSV'

});
```

```js
Export.table.toDrive({

  collection:grid_dataset,

  description:'grid',

  fileFormat:'GeoJSON'

});
```

```js
Export.image.toDrive({

  image:lst_guwahati,

  description:'temperature',

  region:guwahati.geometry(),

  scale:30,

  crs:'EPSG:4326',

  maxPixels:1e13,

  fileFormat:'GeoTIFF'

});
```

```js
Export.image.toDrive({

  image:ndvi_guwahati,

  description:'ndvi',

  region:guwahati.geometry(),

  scale:30,

  crs:'EPSG:4326',

  maxPixels:1e13,

  fileFormat:'GeoTIFF'

});
```

**`Export.table` versus `Export.image`.** They export the two different kinds of Earth Engine data:

| | `Export.table.toDrive` | `Export.image.toDrive` |
|---|---|---|
| Input | a `FeatureCollection` — vector features with properties | an `ee.Image` — a raster of pixels |
| Key argument | `collection:` | `image:` |
| Output formats used here | `CSV`, `GeoJSON` | `GeoTIFF` |
| Needs a resolution? | No — features have exact coordinates | **Yes** — `scale` and `crs` decide how the continuous image is sampled into a pixel grid |
| Needs a region? | No — the collection *is* the extent | **Yes** — `region` bounds what gets written |

The two table exports write the *same* `grid_dataset` in two formats. The CSV is the tabular contract the downstream Python reads; the GeoJSON carries the same rows with geometry as first-class structure, which is what mapping tools want. Note that the CSV is not geometry-free — Earth Engine embeds each polygon into a `.geo` column as JSON, which is how `preprocess.py` currently recovers centroids.

For the image exports, the three raster-specific constants:

- **`scale: 30`** — write at 30 m per pixel, Landsat's native resolution. Consistent with every other `scale: 30` in the script.
- **`crs: 'EPSG:4326'`** — write in longitude/latitude degrees. Chosen for maximum interoperability: every GIS and every web map reads 4326 without configuration. The same trade-off as the grid, though: the output pixels are degree-squares, not metre-squares.
- **`maxPixels: 1e13`** — the safety limit again, in the far more permissive form appropriate to whole-image export. Concretely: the boundary's bounding box is about 212 km²; at 30 m each pixel is 900 m², so a full-bbox export is roughly 212,000,000 / 900 ≈ **235,000 pixels**, about eight orders of magnitude below 10¹³. Like the `1e9` elsewhere, it is a guardrail nowhere near binding here; lower it below ~2.4 × 10⁵ and these exports would fail.

**`description`** is the task name shown in the Tasks tab and also the default output filename — so these four produce `dataset.csv`, `grid.geojson`, `temperature.tif` and `ndvi.tif`, matching the module spec's deliverable names.

**Where the files go.** `toDrive` means the runner's **Google Drive**, by default into a folder named `EarthEngineExports`. Not the repository, not your local disk, not anywhere automatic. Getting them into the repo is a manual download-and-copy step. This is the second thing that trips up first-time users and it is covered next.

### 17. Visualization

```js
Map.addLayer(

  heat_risk,

  {

    min:0,

    max:0.6,

    palette:[

      '006400',

      'ffff00',

      'ff9900',

      'ff0000',

      '800000'

    ]

  },

  'Urban Heat Risk Map'

);
```

`Map.addLayer(image, visParams, name)` draws a layer on the interactive map in the Code Editor. This is display only — it changes nothing about the exported data.

The `min`/`max` pair says which value maps to the first palette colour and which to the last; values outside are drawn at the endpoint colours. `[0, 0.6]` was chosen to spread the contrast across where most `Heat_Risk` values actually fall rather than across its theoretical [−1, +1] range, which would waste most of the palette on empty territory. The five hex colours run dark green → yellow → orange → red → dark red, the conventional cool-to-hot ramp, interpolated between.

Two more layers follow — the boundary in black, and the grid in white, the latter labelled *"Grid display (optional)"* in a comment because drawing 8,144 polygons is slow and it is reasonable to comment out. Finally:

```js
Map.centerObject(

  guwahati,

  12

);
```

Centres and zooms the map on the boundary at zoom level 12, roughly city scale, so that pressing Run lands you looking at Guwahati rather than at the whole planet.

---

## How to actually run it

Everything above is inert until somebody executes it. Here is the full path from a clone to files in the repository.

**1. Get an Earth Engine account.** Go to [earthengine.google.com](https://earthengine.google.com/) and register a Google account for Earth Engine. Current Earth Engine also requires a **Google Cloud project** to be associated with your account; the sign-up flow walks you through creating one. This is the slowest step and it can involve a wait for approval. Non-commercial and research use is free.

**2. Open the Code Editor.** [code.earthengine.google.com](https://code.earthengine.google.com/). Three panels: script editor in the middle, Console/Inspector/Tasks tabs on the right, map at the bottom, and an Assets browser on the left.

**3. Upload the boundary as an asset — this is the step people miss.** The asset path hard-coded at lines 29–31, `projects/urban-heat-guwahati/assets/guwahati_boundary`, lives in the original author's private cloud project. **You cannot read it.** Running the script unmodified will fail. So:

- In the left panel, open the **Assets** tab and choose **New → Table Upload → GeoJSON file** (or Shapefile).
- Upload `Remote Sensing & Data Engineering/Boundary/guwahati_boundary.geojson` from your clone.
- Give it an asset ID. It will end up at `projects/<your-cloud-project>/assets/<name>`.
- Wait for the ingestion task to finish — it appears in the Tasks tab and takes a minute or two for a file this small.
- Copy the finished asset's full path from the Assets browser.

**4. Paste the script and edit line 30.** Copy the whole of `urban_heat_analysis.js` into a new script in the Code Editor, then replace the asset string on **line 30** with your own path from step 3. This is the only edit required.

**5. Press Run.** The map draws, and the Console fills with the `print` output — image count, LST/NDVI/NDBI/land-cover/heat-risk statistics, five sample rows. Sanity-check these before going further, in this order:

| Check | What you want |
|---|---|
| `Number of Landsat Images` | more than a handful; if it is 0 or 1 the boundary or dates are wrong |
| `NDVI Statistics` max | around 0.8. **If it is around 0.39 the rescale is not in effect** |
| `LST Statistics` | a plausible Celsius range, roughly 20–35 for Guwahati |
| `Number of Grid Cells` | thousands, on the order of 8,000 |
| `Sample Grid Dataset` | five rows with all eight properties populated |

**6. Start the export tasks — Run alone produces no files.** This is the second thing that traps first-time users. `Export.*` calls do **not** export. They *register* a task. Open the **Tasks** tab on the right and you will find four entries queued: `dataset`, `grid`, `temperature`, `ndvi`. Each has a **RUN** button, and each must be clicked individually. A confirmation dialog appears for each, where you can set the destination Drive folder and filename.

Expect the table exports to take a while: §12 runs six `reduceRegion` calls across 8,144 cells, and all of that work happens when the task runs, not when you pressed Run.

**7. Download from Drive and place the files.** When a task completes, its output is in your Google Drive (default folder `EarthEngineExports`). Download all four, then copy them into the repository:

| Downloaded | Goes to |
|---|---|
| `dataset.csv` | `Remote Sensing & Data Engineering/Dataset/` |
| `grid.geojson` | `Remote Sensing & Data Engineering/Dataset/` (note the ML module also produces a `grid.geojson` of its own, from the CSV — see [`01-architecture.md`](./01-architecture.md)) |
| `temperature.tif` | `Remote Sensing & Data Engineering/Results/` |
| `ndvi.tif` | `Remote Sensing & Data Engineering/Results/` |

The downstream Python currently reads `Dataset/Guwahati_Urban_Heat_Dataset.csv`, so replacing the data means either renaming the new export to that filename or updating the consumers. Check the column expectations in [`07-data-contracts.md`](./07-data-contracts.md) before doing either — the new export has five columns the old one does not (`Latitude`, `Longitude`, `NDBI`, `LandCover`, `Vegetation`).

### The two things that will trip you up

1. **The asset path is private.** Symptom: an error about the asset not being found or not being readable. Fix: steps 3 and 4.
2. **Pressing Run does not produce files.** Symptom: the map renders, the Console looks healthy, and there is nothing anywhere to download. Fix: step 6 — open the Tasks tab and start each of the four tasks by hand.

---

## What is still blocked, and which files are stale

The situation is precise and worth stating exactly, because it is easy to misread in either direction.

**The script is correct. The data is not.** Every fix described in the [SPEC_AUDIT](../Remote%20Sensing%20%26%20Data%20Engineering/SPEC_AUDIT.md)'s "How to close the gaps" section has been applied to `urban_heat_analysis.js`: the surface-reflectance rescale, the `QA_PIXEL` mask, NDBI, WorldCover land cover and vegetation, per-cell latitude/longitude, the GeoJSON grid export, both GeoTIFF exports, and the renamed CSV export. The file grew from 12 sections to 17. (The audit's own section numbering is pre-rewrite; it carries a mapping table at the top for that reason.)

What has *not* happened is a run. Nobody has executed the corrected script, because doing so needs an Earth Engine account and, in the original setup, access to a private asset. So the committed dataset is still the output of the pre-fix code.

**Which committed files are stale:**

| File | Status |
|---|---|
| `Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv` | **Stale.** 8,144 data rows plus a header. Its columns are `system:index, Heat_Risk, LST, NDVI, count, grid_id, .geo` — no `Latitude`, no `Longitude`, no `NDBI`, no `LandCover`, no `Vegetation`. Its `NDVI` column was computed without the rescale and tops out at 0.386. Its `Heat_Risk` is derived from that NDVI and is biased high. Its `LST` was computed with the correct arithmetic but from a composite with no per-pixel cloud mask. |
| `Remote Sensing & Data Engineering/Results/heat_risk_map.jpeg` | **Stale.** The only file in `Results/`, rendered from the pre-fix heat risk. |
| `temperature.tif`, `ndvi.tif` | **Absent.** The export code exists in §16; no run has produced them. `Results/` contains only the JPEG. (The module's own README lists an LST map and an NDVI map among its generated outputs — that claim is not backed by anything on disk.) |
| `grid.geojson` from Earth Engine | **Absent.** The export code exists in §15. The grid polygons currently live only inside the CSV's `.geo` column. The `grid.geojson` the dashboard consumes is a different file, produced by the ML module from that column. |

**Everything downstream inherits the staleness.** Three separate modules built workarounds for the one NDVI line — a quantile-based vegetation split instead of an absolute threshold, and two independent proxy land-cover classifiers standing in for the missing `LandCover` column. All three disappear the moment a corrected dataset exists. The full contamination cascade, and the specific list of code changes that should be made *after* the re-run and not before, is in [`08-limitations.md`](./08-limitations.md).

**Also known-broken in this module:** `QGIS/guwahati_heat_project.qgz` opens with three unresolved layers. It references `./guwahati_boundary.geojson` (which resolves inside `QGIS/`, where the file is not — it is in `Boundary/`), a `.shp` that does not exist anywhere in the repository, and an absolute path into a local `Downloads/` folder. This predates the repository restructure. The fix is to relink to `../Boundary/guwahati_boundary.geojson` and re-save.

---

## Where to next

- [`04-machine-learning.md`](./04-machine-learning.md) — the module that consumes this one's CSV: preprocessing, the regression and what its R² really means, and the tiering rule engine.
- [`07-data-contracts.md`](./07-data-contracts.md) — the exact column schema this module must produce, with types, units and observed ranges.
