"""
Build the full pipeline for ANY city, with no Google Earth Engine account.

WHY THIS EXISTS ALONGSIDE refresh_dataset.py
--------------------------------------------
`backend/refresh_dataset.py` re-measures the committed Guwahati grid through
the Earth Engine Python API. It is the right tool for keeping Guwahati current
and the wrong tool for adding a city, for two reasons:

  1. It deliberately never regenerates the grid -- it reads the existing cell
     polygons out of dataset.csv, because grid_id is the join key for every
     downstream file. A new city has no existing grid to read.
  2. It needs a Google Cloud service account registered with Earth Engine
     (EE_SERVICE_ACCOUNT_JSON). Nobody can add a city without that credential.

This script needs no credential of any kind. It reads the same two archives
through Microsoft's Planetary Computer STAC API, which serves Landsat
Collection 2 Level 2 and ESA WorldCover as public cloud-optimised GeoTIFFs
with anonymous token signing. `pip install -r backend/requirements-city.txt`
and it runs.

THE GRID IS THE SAME LATTICE, NOT A NEW ONE
-------------------------------------------
This matters more than it looks. The committed Guwahati grid_ids decode:

    +102027+29089  ->  col 102027, row 29089
    cell west edge = 102027 * S,  south edge = 29089 * S
    S = 100 / 111319.4908 degrees   (Earth Engine's 100 m scale in EPSG:4326)

That is a GLOBAL lattice anchored at (0, 0), not a per-city numbering. So this
script snaps every city to the same lattice and formats ids the same way. A
cell in Nagpur and a cell in Guwahati carry ids from one coherent scheme,
adjacent cells differ by one in exactly one index, and rebuilding a city from
scratch reproduces its ids exactly -- the property the Earth Engine path had to
freeze the grid to guarantee.

Verified against the committed dataset: 91.65241349286242 / S = 102027.0 and
26.131093299752763 / S = 29089.0, both integers to floating-point precision.

MEASUREMENTS -- same formulas as the Earth Engine script
--------------------------------------------------------
  LST         lwir11 (ST_B10) * 0.00341802 + 149.0 - 273.15   (Kelvin -> C)
  SR          red/nir08/swir16 * 0.0000275 - 0.2              (C2 L2 rescale)
  NDVI        (nir08 - red)   / (nir08 + red)
  NDBI        (swir16 - nir08) / (swir16 + nir08)
  LandCover   ESA WorldCover v200, modal class over the cell
  Vegetation  WorldCover classes 10/20/30/40, areal fraction over the cell
  Heat_Risk   unitScale(LST, lo, hi) - unitScale(NDVI, -0.2, 0.8)

Cloud handling is the same too: scene-level cloud cover under a threshold, a
per-pixel QA_PIXEL mask for dilated cloud / cirrus / cloud / cloud shadow, and
a median composite across the surviving scenes.

WHERE Heat_Risk DELIBERATELY DIFFERS
------------------------------------
The Earth Engine script hardcodes unitScale(LST, 20, 34). Those bounds were
chosen for Guwahati. Applied to Phoenix, where surface temperature clears 55 C
across most of the built-up area, every hot cell saturates at 1.0 and the tiers
stop discriminating.

So the LST scaling bounds are per city: the 2nd and 98th percentiles of that
city's own measured LST, rounded outward to whole degrees. Guwahati's data
yields bounds that reproduce the original behaviour. The bounds actually used
are written into city.json and shown in the dashboard, because they change what
Heat_Risk means -- see docs/08-limitations.md section 5.

Pass --lst-scale 20 34 to force the original fixed bounds.

WHAT IT WRITES
--------------
    frontend/data/cities/<slug>/grid.geojson   the dashboard payload
    frontend/data/cities/<slug>/dataset.csv    the measured grid, same schema
                                               as the committed Guwahati file
    frontend/data/cities/<slug>/ranking.csv    budget-capped funding order
    frontend/data/cities/<slug>/city.json      provenance and headline figures

The intervention rules, the unit rates, the cooling assumptions and the tier
cut points all come from shared/uhi_shared.py, the same module the Guwahati
pipeline uses. There is no second copy of the decision logic here -- that
duplication is the specific mistake docs/05-decision-support.md is about.

Run:
    python backend/build_city.py --preset nagpur
    python backend/build_city.py --bbox 78.42 17.36 78.54 17.46 --name Hyderabad
    python backend/build_city.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402

PRESETS_PATH = Path(__file__).resolve().parent / "city_presets.json"
OUT_ROOT = REPO_DIR / "frontend" / "data" / "cities"
MANIFEST_PATH = REPO_DIR / "frontend" / "data" / "cities.json"

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Earth Engine's 100 m scale expressed in degrees, and the anchor for the
# global lattice every grid_id is an index into. Do not "improve" this constant
# -- it is what makes a rebuilt grid_id match the committed one.
METRES_PER_DEGREE = 111319.4908
CELL_SIZE_DEG = 100.0 / METRES_PER_DEGREE

# Landsat C2 L2 scaling. Published USGS coefficients, identical to the ones in
# the Earth Engine script and refresh_dataset.py.
ST_SCALE, ST_OFFSET = 0.00341802, 149.0
SR_SCALE, SR_OFFSET = 0.0000275, -0.2
KELVIN = 273.15

# QA_PIXEL bit positions to reject: dilated cloud, cirrus, cloud, cloud shadow.
QA_REJECT_BITS = (1, 2, 3, 4)

# WorldCover classes counted as vegetation for the Vegetation fraction, matching
# the Earth Engine script: tree cover, shrubland, grassland, cropland.
VEG_CLASSES = (10, 20, 30, 40)

NDVI_SCALE_LO, NDVI_SCALE_HI = -0.2, 0.8

DATASET_COLUMNS = [
    "system:index", "Heat_Risk", "LST", "LandCover", "Latitude", "Longitude",
    "NDBI", "NDVI", "Vegetation", "count", "grid_id", ".geo",
]


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def metres_per_degree(lat_deg: float) -> tuple[float, float]:
    """WGS84 metres per degree of latitude and of longitude at `lat_deg`.

    Standard series expansion. Used only to report a cell area; nothing in the
    grid construction depends on it.
    """
    phi = math.radians(lat_deg)
    m_lat = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    m_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
    return m_lat, m_lon


def cell_area_m2(lat_deg: float) -> float:
    m_lat, m_lon = metres_per_degree(lat_deg)
    return (m_lat * CELL_SIZE_DEG) * (m_lon * CELL_SIZE_DEG)


def snap_bbox(bbox: list[float]) -> tuple[int, int, int, int]:
    """Snap a bbox outward to whole lattice cells. Returns index bounds."""
    west, south, east, north = bbox
    col0 = math.floor(west / CELL_SIZE_DEG)
    col1 = math.ceil(east / CELL_SIZE_DEG)
    row0 = math.floor(south / CELL_SIZE_DEG)
    row1 = math.ceil(north / CELL_SIZE_DEG)
    return col0, row0, col1, row1


def grid_id(col: int, row: int) -> str:
    """Reproduce the committed id format exactly: '+102027+29089'."""
    return f"{col:+d}{row:+d}"


# --------------------------------------------------------------------------
# imagery
# --------------------------------------------------------------------------

def open_catalog():
    import planetary_computer as pc
    import pystac_client
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def check_gdal():
    """Refuse to run on a GDAL too old to be trusted with NaN nodata.

    Everything downstream depends on one behaviour: when a cloud-masked pixel is
    set to NaN and handed to the warper as src_nodata, `average` and `mode` must
    SKIP it rather than fold it into the result. GDAL 3.12 does -- verified
    directly: averaging a 2x2 block of three 10s and one NaN returns 10.0, and
    mode over three 10s, one 80 and a NaN block returns 10 and NaN respectively.

    On older GDAL that handling is version-dependent, and when it is wrong it is
    wrong SILENTLY: every partially cloudy cell comes back contaminated instead
    of masked, and the output looks entirely reasonable. A hard version floor is
    the only cheap defence against a failure that produces no error.
    """
    import rasterio
    parts = rasterio.__gdal_version__.split(".")
    major, minor = int(parts[0]), int(parts[1])
    if (major, minor) < (3, 5):
        raise SystemExit(
            f"GDAL {rasterio.__gdal_version__} is too old. This script relies on "
            f"the warper skipping NaN nodata under `average` and `mode` "
            f"resampling; older builds fold masked pixels into the result "
            f"silently. Install rasterio with GDAL 3.5 or newer."
        )


def pick_scenes(catalog, bbox, start, end, max_cloud, max_scenes, months=None):
    """Lowest-cloud scenes, spread across every path/row the bbox touches.

    A city bbox can straddle two or three Landsat path/rows. Taking the N
    globally cleanest scenes can then return N scenes that all cover the same
    two thirds of the city and none that cover the rest, leaving a hard empty
    edge in the composite. Selecting per path/row avoids that.
    """
    search = catalog.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=f"{start}/{end}",
        query={
            "eo:cloud_cover": {"lt": max_cloud},
            "platform": {"in": ["landsat-8", "landsat-9"]},
        },
    )
    items = list(search.items())
    if months:
        kept = [it for it in items if it.datetime.month in months]
        print(f"  {len(items)} scenes in window, {len(kept)} inside the "
              f"selected months {sorted(months)}")
        items = kept
    if not items:
        raise SystemExit(
            f"No Landsat 8/9 scenes under {max_cloud}% cloud over {bbox} "
            f"between {start} and {end}. Widen --start/--end, raise "
            f"--max-cloud, or pass --season all."
        )

    by_pathrow: dict[tuple, list] = {}
    for it in items:
        key = (it.properties.get("landsat:wrs_path"), it.properties.get("landsat:wrs_row"))
        by_pathrow.setdefault(key, []).append(it)

    per_group = max(1, max_scenes // max(1, len(by_pathrow)))
    chosen = []
    for key, group in sorted(by_pathrow.items()):
        group.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
        chosen.extend(group[:per_group])

    print(f"  {len(items)} scenes available across {len(by_pathrow)} path/row(s); "
          f"compositing {len(chosen)}")
    return chosen


def padded_window(src, bounds_4326, pad=2):
    """Integer pixel window covering `bounds_4326` in `src`, padded by `pad`.

    Written out longhand rather than chaining Window.round_offsets() and
    .round_lengths(): those two do not compose the way they look like they do --
    round_offsets adjusts width/height to hold the right edge fixed, so calling
    it after round_lengths un-rounds the lengths, and the subsequent int() then
    truncates and drops the last column or row. Flooring the origin and ceiling
    the far edge is unambiguous.
    """
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    src_bounds = transform_bounds("EPSG:4326", src.crs, *bounds_4326)
    w = from_bounds(*src_bounds, transform=src.transform)

    col_off = max(0, math.floor(w.col_off) - pad)
    row_off = max(0, math.floor(w.row_off) - pad)
    col_end = min(src.width, math.ceil(w.col_off + w.width) + pad)
    row_end = min(src.height, math.ceil(w.row_off + w.height) + pad)

    if col_end <= col_off or row_end <= row_off:
        return None  # the raster does not intersect the bbox at all
    return Window(col_off, row_off, col_end - col_off, row_end - row_off)


def grid_bounds(dst_shape, dst_transform):
    import rasterio
    return rasterio.transform.array_bounds(dst_shape[0], dst_shape[1], dst_transform)


def read_to_grid(href, dst_shape, dst_transform, resampling, mask_source=None):
    """Read a remote COG and resample it straight onto the lattice.

    The destination IS the lattice, so aggregation from 30 m (Landsat) or 10 m
    (WorldCover) down to the 100 m cell happens inside the warp. Masked pixels
    are NaN before the warp and the warper skips them -- see check_gdal().
    """
    import rasterio
    from rasterio.warp import reproject

    dst = np.full(dst_shape, np.nan, dtype="float32")

    with rasterio.open(href) as src:
        win = padded_window(src, grid_bounds(dst_shape, dst_transform))
        if win is None:
            return dst

        arr = src.read(1, window=win).astype("float32")
        src_transform = src.window_transform(win)

        # Mask fill BEFORE the scale/offset is applied. Afterwards a fill value
        # of 0 becomes a perfectly plausible -0.2 reflectance or 149 K, and
        # nothing downstream can tell it from a measurement.
        nodata = src.nodata
        arr[arr == (nodata if nodata is not None else 0)] = np.nan

        if mask_source is not None:
            reject = mask_source(src, win)
            if isinstance(reject, str):
                raise ValueError("QA_PIXEL grid mismatch")
            if reject is not None:
                arr[reject] = np.nan

        reproject(
            source=arr,
            destination=dst,
            src_transform=src_transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return dst


def qa_cloud_mask(qa_href):
    """A callable returning the 'reject this pixel' mask for a scene.

    Landsat C2 L2 QA_PIXEL bits: 0 fill, 1 dilated cloud, 2 cirrus, 3 cloud,
    4 cloud shadow. Bits 1-4 are rejected.
    """
    import rasterio

    def _mask(src, win):
        with rasterio.open(qa_href) as qsrc:
            # The window was computed against the BAND's transform, so reusing
            # it on the QA raster is only valid if the two share a grid. For
            # Landsat they always do. Checking dimensions alone would pass a
            # raster of the same size on a shifted origin and mask the wrong
            # pixels, so compare what actually matters -- and say so out loud
            # rather than dropping the cloud mask in silence, because an
            # unmasked scene produces a warm, clean-looking, wrong composite.
            if qsrc.transform != src.transform or qsrc.crs != src.crs:
                warnings.warn(
                    f"QA_PIXEL grid does not match the band grid for {qa_href}; "
                    f"this scene would be composited WITHOUT a cloud mask, so it "
                    f"is being dropped instead.")
                return "mismatch"
            qa = qsrc.read(1, window=win)
        reject = np.zeros(qa.shape, dtype=bool)
        for bit in QA_REJECT_BITS:
            reject |= (qa & (1 << bit)) > 0
        return reject

    return _mask


def composite_landsat(items, dst_shape, dst_transform):
    """Per-scene cloud-masked reads, then a per-cell median across scenes."""
    import planetary_computer as pc
    import rasterio
    from rasterio.enums import Resampling

    bands = {"lwir11": [], "red": [], "nir08": [], "swir16": []}
    used = 0
    for i, item in enumerate(items, 1):
        # Planetary Computer asset URLs are SAS-signed and expire in about an
        # hour. Signing once at search time is fine for a small city and fails
        # partway through a large one, so re-sign immediately before use.
        assets = pc.sign(item).assets
        if not all(b in assets for b in bands) or "qa_pixel" not in assets:
            print(f"  scene {i}/{len(items)} {item.id}: missing an asset, skipped")
            continue

        masker = qa_cloud_mask(assets["qa_pixel"].href)
        try:
            scene = {
                b: read_to_grid(assets[b].href, dst_shape, dst_transform,
                                Resampling.average, mask_source=masker)
                for b in bands
            }
        except (rasterio.errors.RasterioError, ValueError) as exc:
            # Deliberately narrow. A blanket `except Exception` here turns a
            # systematic failure -- an expired token, a bad GDAL build, a typo
            # in an asset key -- into "every scene skipped", which reads like a
            # data problem and sends you looking in the wrong place.
            print(f"  scene {i}/{len(items)} {item.id}: read failed ({exc})")
            continue

        if np.all(np.isnan(scene["lwir11"])):
            print(f"  scene {i}/{len(items)} {item.id}: no clear pixels over the bbox")
            continue

        for b in bands:
            bands[b].append(scene[b])
        used += 1
        covered = np.mean(~np.isnan(scene["lwir11"])) * 100
        print(f"  scene {i}/{len(items)} {item.id} "
              f"({item.datetime.date()}, cloud {item.properties.get('eo:cloud_cover', 0):.0f}%) "
              f"-> {covered:.0f}% of cells")

    if used == 0:
        raise SystemExit("Every candidate scene was empty or unreadable over this bbox.")

    stack = np.stack(bands["lwir11"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # all-NaN cells
        out = {b: np.nanmedian(np.stack(v), axis=0) for b, v in bands.items()}

    # Per-cell observation count. Cells differ in how many scenes actually saw
    # them -- a cell at the edge of one path/row may rest on a single
    # observation while one in the overlap rests on eight. That is invisible in
    # the composite and it is exactly what someone auditing an odd cell needs,
    # so it is carried through to dataset.csv rather than a hardcoded 1.
    out["_obs_count"] = np.sum(~np.isnan(stack), axis=0)
    out["_scenes_used"] = used
    return out


def worldcover(catalog, bbox, dst_shape, dst_transform):
    """Modal land-cover class and vegetated fraction, from ESA WorldCover v200."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject

    items = [
        it for it in catalog.search(collections=["esa-worldcover"], bbox=bbox).items()
        if "v200" in it.id
    ]
    if not items:
        raise SystemExit(f"No ESA WorldCover v200 tile covers {bbox}.")

    print(f"  {len(items)} WorldCover v200 tile(s): {[i.id for i in items]}")

    mode = np.full(dst_shape, np.nan, dtype="float32")
    veg = np.full(dst_shape, np.nan, dtype="float32")
    bounds = grid_bounds(dst_shape, dst_transform)

    for it in items:
        href = it.assets["map"].href
        m = read_to_grid(href, dst_shape, dst_transform, Resampling.mode)
        np.copyto(mode, m, where=~np.isnan(m))

        # Vegetated fraction. Binarise at 10 m FIRST and average the 0/1 mask;
        # averaging the class codes themselves would produce a number halfway
        # between "built-up" and "water" and mean nothing.
        with rasterio.open(href) as src:
            win = padded_window(src, bounds)
            if win is None:
                continue
            classes = src.read(1, window=win)
            binary = np.isin(classes, VEG_CLASSES).astype("float32")
            binary[classes == 0] = np.nan  # WorldCover uses 0 for no data
            dst = np.full(dst_shape, np.nan, dtype="float32")
            reproject(
                source=binary, destination=dst,
                src_transform=src.window_transform(win), src_crs=src.crs,
                src_nodata=np.nan,
                dst_transform=dst_transform, dst_crs="EPSG:4326", dst_nodata=np.nan,
                resampling=Resampling.average,
            )
        np.copyto(veg, dst, where=~np.isnan(dst))

    return mode, veg


# --------------------------------------------------------------------------
# pipeline (shared rules, no second copy of the decision logic)
# --------------------------------------------------------------------------

def unit_scale(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def build_dataframe(cols, rows, data, lst_scale):
    ncols, nrows = len(cols), len(rows)
    col_grid, row_grid = np.meshgrid(cols, rows)

    lst = data["lwir11"] * ST_SCALE + ST_OFFSET - KELVIN
    # Clamped to physical reflectance. C2 L2 surface reflectance goes slightly
    # negative over deep water and terrain shadow, where the atmospheric
    # correction over-subtracts. Left unclamped those pixels drive NDVI and NDBI
    # outside [-1, 1] and, worse, can flip their sign - a water cell reading as
    # dense vegetation. Clamping before the ratio is the standard handling.
    red = np.clip(data["red"] * SR_SCALE + SR_OFFSET, 0.0, 1.0)
    nir = np.clip(data["nir08"] * SR_SCALE + SR_OFFSET, 0.0, 1.0)
    swir = np.clip(data["swir16"] * SR_SCALE + SR_OFFSET, 0.0, 1.0)

    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndbi = (swir - nir) / (swir + nir)

    df = pd.DataFrame({
        "col": col_grid.ravel(),
        "row": row_grid.ravel(),
        "LST": lst.ravel(),
        "NDVI": ndvi.ravel(),
        "NDBI": ndbi.ravel(),
        "LandCover": data["landcover"].ravel(),
        "Vegetation": data["vegetation"].ravel(),
        "obs_count": data["_obs_count"].ravel(),
    })

    before = len(df)
    df = df.dropna(subset=["LST", "NDVI", "LandCover"]).reset_index(drop=True)
    print(f"  {len(df):,} cells with complete measurements "
          f"({before - len(df):,} dropped: cloud, scene edge or outside coverage)")
    if df.empty:
        raise SystemExit("No cell survived. Widen the date window or the bbox.")

    lo, hi = lst_scale
    df["Heat_Risk"] = (unit_scale(df["LST"], lo, hi)
                       - unit_scale(df["NDVI"], NDVI_SCALE_LO, NDVI_SCALE_HI))

    df["Longitude"] = (df["col"] + 0.5) * CELL_SIZE_DEG
    df["Latitude"] = (df["row"] + 0.5) * CELL_SIZE_DEG
    df["grid_id"] = [grid_id(c, r) for c, r in zip(df["col"], df["row"])]
    return df


def tier(df):
    """Same quantile convention and the same constants as the ML module."""
    hq = shared.TIERING["high_quantile"]
    lq = shared.TIERING["low_quantile"]
    hi_cut = df["Heat_Risk"].quantile(hq)
    lo_cut = df["Heat_Risk"].quantile(lq)
    priority = np.where(df["Heat_Risk"] >= hi_cut, "High",
                        np.where(df["Heat_Risk"] <= lo_cut, "Low", "Medium"))
    return priority, float(hi_cut), float(lo_cut)


def apply_rules(df):
    labels, reasons = [], []
    for code, prio in zip(df["LandCover"], df["priority"]):
        label = shared.land_cover_label(code)
        action, reason = shared.assign_action(label, prio)
        labels.append(action)
        reasons.append(reason)
    df["land_cover"] = [shared.land_cover_label(c) for c in df["LandCover"]]
    df["recommended_action"] = labels
    df["exclusion_reason"] = reasons

    # The safety rule the whole project rests on. Assert it here too rather
    # than trusting that it held upstream.
    never = df[df["land_cover"].isin(shared.NEVER_TOUCH)]
    bad = never[never["recommended_action"] != "None"]
    if len(bad):
        raise AssertionError(
            f"{len(bad)} never-touch cells were assigned an intervention: "
            f"{bad['land_cover'].unique().tolist()}"
        )

    area = df["Latitude"].map(cell_area_m2)
    df["cell_area_m2"] = area
    df["cost_estimate"] = [
        shared.action_cost(a, m) for a, m in zip(df["recommended_action"], area)
    ]
    df["cooling_c"] = df["recommended_action"].map(shared.action_cooling_c)
    with np.errstate(invalid="ignore", divide="ignore"):
        df["cooling_per_rupee"] = np.where(
            df["cost_estimate"] > 0, df["cooling_c"] / df["cost_estimate"], 0.0
        )
    return df


def add_plan_rank(df):
    """The pipeline's funding order, carried into the grid.

    The dashboard re-runs the budget client-side over whatever subset the user
    has filtered to, so it needs the priority order in the file. It must not
    re-derive it: `temperature` ships at 1 dp and cooling_per_rupee has only
    three distinct values, so thousands of cells tie at a precision the pipeline
    never saw, and the browser funds a different set of the same size and cost.

    Same keys and the same reasoning as add_plan_rank() in
    export_grid_geojson.py. Cooling per rupee is an attribute of the MEASURE,
    not of the cell, so it is computed from the median cost per action: pricing
    each cell from its own polygon makes cost vary by a few rupees between
    identical actions, which turns geometric noise into thousands of distinct
    scores in the sixth decimal and leaves LST unused as a tie-break.

    Non-actionable cells get 0 -- never funded at any budget.
    """
    actionable = df["recommended_action"] != "None"
    ranked = df[actionable].copy()

    unit_cost = ranked.groupby("recommended_action")["cost_estimate"].transform("median")
    ranked["_cpr"] = ranked["cooling_c"] / unit_cost
    ranked = ranked.sort_values(
        ["_cpr", "LST", "grid_id"],
        ascending=[False, False, True],
        kind="mergesort",
    )

    df["plan_rank"] = 0
    df.loc[ranked.index, "plan_rank"] = range(1, len(ranked) + 1)
    return df


def rank(df, budget):
    """ranking.csv, in the same order the dashboard funds cells in."""
    actionable = df[df["recommended_action"] != "None"].copy()
    actionable = actionable.sort_values("plan_rank", kind="mergesort").reset_index(drop=True)
    actionable["rank"] = actionable["plan_rank"]
    actionable["cumulative_cost"] = actionable["cost_estimate"].cumsum()
    actionable["within_budget"] = actionable["cumulative_cost"] <= budget
    return actionable


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# administrative boundary
# --------------------------------------------------------------------------

# OpenStreetMap's geocoder. No account, no key, no quota beyond a courtesy
# rate limit of one request a second, which build_city.py honours because it
# makes exactly one call per build.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Above this, a city's own boundary is not worth tiling at 100 m: Phoenix's
# city limits are 1,340 km2 and would be 162,000 cells, four times Chennai,
# for a city that is in the preset list only as a cost-model example. Cities
# over the cap keep their preset window and say so in city.json rather than
# being given a shape they do not have.
MAX_BOUNDARY_CELLS = 60_000


def fetch_boundary(name, region, timeout=30):
    """The city's administrative outline, or None.

    Returns (shapely geometry, description) so city.json can record which
    entity was actually used -- "Nagpur City" and "Nagpur district" are both
    plausible answers to a search for Nagpur and they differ by a factor of
    twenty in area.

    Preference order matters. Nominatim ranks a district above a city for
    several Indian names, and the district polygon for Ahmedabad is 775,000
    cells against a city core of a few thousand. `addresstype == "city"` is
    place_rank 16 and a district is rank 10, so the filter is exact rather
    than heuristic.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    query = ", ".join(x for x in (name, region) if x)
    url = NOMINATIM_URL + "?" + urllib.parse.urlencode({
        "q": query, "format": "jsonv2", "polygon_geojson": 1, "limit": 8,
    })
    request = urllib.request.Request(url, headers={
        # Nominatim's usage policy requires an identifying User-Agent and
        # returns 403 without one.
        "User-Agent": "urban-heat-island-mitigation-simulation/1.0 "
                      "(https://github.com/ankamteja/urban-heat-island-mitigation-simulation)",
    })

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            hits = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  boundary lookup failed ({exc}); using the bbox unclipped")
        return None, None

    polygons = [h for h in hits
                if (h.get("geojson") or {}).get("type") in ("Polygon", "MultiPolygon")]
    if not polygons:
        print("  no administrative polygon found; using the bbox unclipped")
        return None, None

    cities = [h for h in polygons if h.get("addresstype") == "city"]
    hit = (cities or polygons)[0]
    if not cities:
        print("  no city-level polygon; falling back to the broadest match")

    from shapely.geometry import shape as to_shape
    return to_shape(hit["geojson"]), hit.get("display_name", query)


def boundary_cell_count(geometry):
    """Cells in the geometry's bounding box, at the lattice step."""
    west, south, east, north = geometry.bounds
    return ((math.floor(east / CELL_SIZE_DEG) - math.floor(west / CELL_SIZE_DEG) + 1)
            * (math.floor(north / CELL_SIZE_DEG) - math.floor(south / CELL_SIZE_DEG) + 1))


def clip_to_boundary(df, geometry):
    """Drop cells whose centre falls outside the boundary.

    The centre, not any overlap: a cell is in the city or it is not, and an
    overlap test would keep a rim of cells that are mostly outside it and
    whose temperature is mostly not the city's.

    Uses a prepared geometry -- an unprepared `contains` over tens of
    thousands of points against a 3,500-vertex multipolygon walks every edge
    every time and turns a two-second step into minutes.
    """
    from shapely import points
    from shapely.prepared import prep

    inside = prep(geometry)
    centres = points(df["Longitude"].to_numpy(), df["Latitude"].to_numpy())
    keep = np.fromiter((inside.contains(pt) for pt in centres), dtype=bool, count=len(df))
    return df[keep].reset_index(drop=True)


def cell_polygon(col, row, decimals=6):
    w = round(col * CELL_SIZE_DEG, decimals)
    e = round((col + 1) * CELL_SIZE_DEG, decimals)
    s = round(row * CELL_SIZE_DEG, decimals)
    n = round((row + 1) * CELL_SIZE_DEG, decimals)
    return [[[w, s], [e, s], [e, n], [w, n], [w, s]]]


def write_outputs(slug, meta, df, ranked, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. grid.geojson -- exactly the seven properties the frontend reads.
    features = []
    for r in df.itertuples(index=False):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": cell_polygon(r.col, r.row)},
            "properties": {
                "grid_id": r.grid_id,
                "temperature": round(float(r.LST), 1),
                "ndvi": round(float(r.NDVI), 3),
                "ndbi": round(float(r.NDBI), 3),
                "land_cover": str(r.land_cover),
                "priority": str(r.priority),
                "recommended_action": str(r.recommended_action),
                "exclusion_reason": str(r.exclusion_reason or ""),
                "cost_estimate": int(round(r.cost_estimate)),
                "cooling_c": round(float(r.cooling_c), 1),
                # The pipeline's funding order. 0 = never funded at any budget.
                # int, because the browser sorts on it.
                "plan_rank": int(r.plan_rank),
            },
        })
    validate_features(features)
    payload = json.dumps({"type": "FeatureCollection", "features": features})
    (out_dir / "grid.geojson").write_text(payload, encoding="utf-8")

    # The committed Guwahati grid ships with a sha256 in data/release.json and
    # the dashboard refuses to load it unchecked. A built city gets the same
    # treatment rather than a weaker guarantee: the digest goes in city.json and
    # doubles as the cache-busting key, so a rebuilt city cannot be served from
    # a stale browser cache.
    meta["grid_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    meta["release_id"] = meta["grid_sha256"][:12]

    # 2. dataset.csv -- same column set and order as the committed Guwahati file,
    #    so anything that reads one reads the other.
    ds = pd.DataFrame({
        "system:index": df["grid_id"],
        "Heat_Risk": df["Heat_Risk"],
        "LST": df["LST"],
        "LandCover": df["LandCover"].astype(float),
        "Latitude": df["Latitude"],
        "Longitude": df["Longitude"],
        "NDBI": df["NDBI"],
        "NDVI": df["NDVI"],
        "Vegetation": df["Vegetation"],
        "count": df["obs_count"].astype(int),
        "grid_id": df["grid_id"],
        ".geo": [
            json.dumps({"geodesic": False, "type": "Polygon",
                        "coordinates": cell_polygon(c, r, decimals=12)})
            for c, r in zip(df["col"], df["row"])
        ],
    })[DATASET_COLUMNS]
    ds.to_csv(out_dir / "dataset.csv", index=False)

    # 3. ranking.csv -- the funding order.
    ranked[[
        "rank", "grid_id", "Latitude", "Longitude", "land_cover", "priority",
        "LST", "NDVI", "recommended_action", "cost_estimate", "cooling_c",
        "cooling_per_rupee", "cumulative_cost", "within_budget",
    ]].to_csv(out_dir / "ranking.csv", index=False)

    # 4. city.json -- provenance and the headline figures, so the dashboard
    #    never has to recompute them to render a card.
    (out_dir / "city.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    for name in ("grid.geojson", "dataset.csv", "ranking.csv", "city.json"):
        size = (out_dir / name).stat().st_size / 1_048_576
        print(f"  wrote {out_dir.relative_to(REPO_DIR)}/{name} ({size:.2f} MB)")


def validate_features(features):
    """Same contract check export_grid_geojson.py applies. A city built here
    must be indistinguishable to the frontend from the committed Guwahati
    file."""
    expected = {"grid_id", "temperature", "ndvi", "ndbi", "land_cover",
                "priority", "recommended_action", "exclusion_reason",
                "cost_estimate", "cooling_c", "plan_rank"}
    if not features:
        raise ValueError("No features produced")
    for i, f in enumerate(features):
        keys = set(f["properties"])
        if keys != expected:
            raise ValueError(f"Feature {i} property mismatch: "
                             f"unexpected {sorted(keys - expected)}, "
                             f"missing {sorted(expected - keys)}")
        if f["geometry"]["type"] != "Polygon":
            raise ValueError(f"Feature {i} geometry is not a Polygon")
        if not isinstance(f["properties"]["cost_estimate"], int):
            raise ValueError(f"Feature {i} cost_estimate must be int")
        if not isinstance(f["properties"]["plan_rank"], int):
            raise ValueError(
                f"Feature {i} plan_rank must be int - the browser sorts on it")
        if f["properties"]["recommended_action"] not in shared.VALID_ACTIONS:
            raise ValueError(
                f"Feature {i} action {f['properties']['recommended_action']!r} "
                f"not in {sorted(shared.VALID_ACTIONS)}")


def update_manifest():
    """Rebuild frontend/data/cities.json from whatever city.json files exist.

    Derived, never hand-edited, so it cannot drift from what is actually on
    disk -- the failure mode that made the dashboard serve a stale grid before.
    """
    entries = []

    legacy = REPO_DIR / "frontend" / "data" / "grid.geojson"
    if legacy.exists():
        entry = {
            "slug": "guwahati",
            "name": "Guwahati",
            "region": "Assam, India",
            "path": "data/grid.geojson",
            "source": "Google Earth Engine (Landsat 8 C2 L2 + ESA WorldCover v200)",
            "cost_basis_applies": True,
            "builtin": True,
        }
        # The committed city's checksum lives in release.json, not in a
        # city.json. Copy it in so every manifest entry carries the same
        # integrity token and the dashboard has one code path for all cities.
        release = REPO_DIR / "frontend" / "data" / "release.json"
        if release.exists():
            r = json.loads(release.read_text(encoding="utf-8"))
            if r.get("grid_sha256"):
                entry["grid_sha256"] = r["grid_sha256"]
                entry["release_id"] = r.get("release_id", r["grid_sha256"][:12])
            if r.get("cell_count"):
                entry["cells"] = r["cell_count"]
            if r.get("total_cost_inr"):
                entry["cost_all_actionable_inr"] = r["total_cost_inr"]
        entries.append(entry)

    for city_json in sorted(OUT_ROOT.glob("*/city.json")):
        meta = json.loads(city_json.read_text(encoding="utf-8"))
        if meta.get("slug") == "guwahati":
            continue  # the committed Earth Engine build stays canonical
        meta["path"] = f"data/cities/{meta['slug']}/grid.geojson"
        meta["builtin"] = False
        entries.append(meta)

    MANIFEST_PATH.write_text(json.dumps({"cities": entries}, indent=2), encoding="utf-8")
    print(f"  wrote {MANIFEST_PATH.relative_to(REPO_DIR)} ({len(entries)} cities)")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def resolve_city(args):
    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    if args.preset:
        if args.preset not in presets:
            raise SystemExit(f"Unknown preset {args.preset!r}. "
                             f"Known: {sorted(k for k in presets if not k.startswith('_'))}")
        p = presets[args.preset]
        return args.preset, p["name"], p["region"], p["bbox"], p["cost_basis_applies"]

    if not args.bbox:
        raise SystemExit("Pass --preset NAME or --bbox W S E N.")
    name = args.name or "Custom area"
    slug = args.slug or name.lower().replace(" ", "-").replace(",", "")
    return slug, name, args.region or "", list(args.bbox), args.cost_basis


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", help="a city from backend/city_presets.json")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    ap.add_argument("--no-clip", action="store_true",
                    help="Skip the boundary lookup and tile the raw bbox. Use "
                         "when offline, or when the geocoder returns the wrong "
                         "entity for a city.")
    ap.add_argument("--name")
    ap.add_argument("--slug")
    ap.add_argument("--region", default="")
    ap.add_argument("--cost-basis", action="store_true",
                    help="assert the Indian INR rate table applies to this city")
    ap.add_argument("--start", help="composite window start, YYYY-MM-DD")
    ap.add_argument("--end", help="composite window end, YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=730,
                    help="if --start/--end are omitted, look back this many days")
    ap.add_argument("--max-cloud", type=float, default=20.0)
    ap.add_argument("--max-scenes", type=int, default=8)
    ap.add_argument("--season", choices=["hot", "all"], default="hot",
                    help="'hot' composites only the local hot season "
                         "(Mar-Jun north, Nov-Feb south); 'all' uses every "
                         "scene in the window")
    ap.add_argument("--lst-scale", nargs=2, type=float, metavar=("LO", "HI"),
                    help="force fixed Heat_Risk LST bounds (Guwahati used 20 34)")
    ap.add_argument("--list", action="store_true", help="list presets and exit")
    args = ap.parse_args()

    if args.list:
        presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        for k, v in presets.items():
            if k.startswith("_"):
                continue
            flag = "" if v["cost_basis_applies"] else "   [INR cost model does NOT apply]"
            print(f"  {k:<11} {v['name']}, {v['region']}{flag}")
        return

    slug, name, region, bbox, cost_ok = resolve_city(args)
    end = args.end or date.today().isoformat()
    start = args.start or (date.fromisoformat(end) - timedelta(days=args.days)).isoformat()

    print(f"\n{name} ({region})")

    # The study area. A raw bbox makes every city a rectangle, which is why
    # the built cities looked nothing like Guwahati: the Earth Engine script
    # clipped Guwahati to a geoBoundaries polygon and this script had no
    # equivalent step.
    #
    # When the city's own boundary is small enough to tile at 100 m, it
    # replaces the preset bbox outright and the city gets its true outline.
    # When it is not -- Phoenix's city limits are 1,340 km2 -- the preset
    # window is kept and city.json records that it is a window, because a
    # centred crop of a much larger city is a rectangle whatever we call it.
    boundary, boundary_name = (None, None)
    if not args.no_clip:
        boundary, boundary_name = fetch_boundary(name, region)

    boundary_mode = "none"
    if boundary is not None:
        n_cells = boundary_cell_count(boundary)
        if n_cells <= MAX_BOUNDARY_CELLS:
            bbox = list(boundary.bounds)
            boundary_mode = "full"
            print(f"  boundary: {boundary_name} ({n_cells:,} cells in its bbox)")
        else:
            boundary_mode = "window"
            print(f"  boundary: {boundary_name} is {n_cells:,} cells, over the "
                  f"{MAX_BOUNDARY_CELLS:,} cap -- keeping the preset window")

    print(f"  bbox {[round(v, 4) for v in bbox]}  window {start} to {end}")

    col0, row0, col1, row1 = snap_bbox(bbox)
    cols = np.arange(col0, col1)
    rows = np.arange(row0, row1)
    # Raster row 0 is the NORTH edge, so the lattice rows are reversed for the
    # array and the transform.
    rows_desc = rows[::-1]
    shape = (len(rows), len(cols))

    from rasterio.transform import from_origin
    transform = from_origin(col0 * CELL_SIZE_DEG, (row1) * CELL_SIZE_DEG,
                            CELL_SIZE_DEG, CELL_SIZE_DEG)
    # The transform and the grid_id maths have to describe the same cells. If
    # they ever drift, every value lands in the wrong cell and nothing errors.
    assert math.isclose(transform.a, CELL_SIZE_DEG) and math.isclose(-transform.e, CELL_SIZE_DEG), \
        "raster transform pixel size does not match the lattice cell size"
    assert math.isclose(transform.c, col0 * CELL_SIZE_DEG), \
        "raster origin is not on a lattice boundary"
    print(f"  lattice {shape[1]} x {shape[0]} = {shape[0] * shape[1]:,} cells "
          f"at {CELL_SIZE_DEG:.8f} deg (~100 m)")

    # Season. A median over two full years averages the hot season together
    # with the cool one, which is the wrong composite for a heat study: it
    # understates the peak the whole project is about. Default to the local hot
    # season, hemisphere-aware, and record which months were used.
    centre_lat = (bbox[1] + bbox[3]) / 2
    if args.season == "all":
        months, season_label = None, "all months"
    else:
        months = ({3, 4, 5, 6} if centre_lat >= 0 else {11, 12, 1, 2})
        season_label = ("Mar-Jun (northern hot season)" if centre_lat >= 0
                        else "Nov-Feb (southern hot season)")
    print(f"  season filter: {season_label}")

    check_gdal()
    catalog = open_catalog()
    items = pick_scenes(catalog, bbox, start, end, args.max_cloud, args.max_scenes,
                        months=months)
    data = composite_landsat(items, shape, transform)
    lc, veg = worldcover(catalog, bbox, shape, transform)
    data["landcover"] = lc
    data["vegetation"] = veg

    lst_raw = data["lwir11"] * ST_SCALE + ST_OFFSET - KELVIN
    finite = lst_raw[np.isfinite(lst_raw)]
    if args.lst_scale:
        lst_scale = tuple(args.lst_scale)
        scale_basis = "fixed, supplied on the command line"
    else:
        lo = math.floor(np.percentile(finite, 2))
        hi = math.ceil(np.percentile(finite, 98))
        lst_scale = (float(lo), float(hi))
        scale_basis = "this city's own 2nd/98th LST percentiles, rounded outward"
    print(f"  Heat_Risk LST bounds {lst_scale[0]:.0f}-{lst_scale[1]:.0f} C ({scale_basis})")

    df = build_dataframe(cols, rows_desc, data, lst_scale)

    # Clip before tiering, not after. Priority tiers are quantiles over the
    # study area, so cutting them from cells that are then discarded would
    # tier the city against land outside it.
    if boundary is not None:
        before = len(df)
        df = clip_to_boundary(df, boundary)
        if df.empty:
            raise SystemExit(
                f"No cell fell inside {boundary_name}. Check the boundary match, "
                f"or pass --no-clip.")
        print(f"  {len(df):,} cells inside {boundary_name} "
              f"({before - len(df):,} dropped outside it)")

    df["priority"], hi_cut, lo_cut = tier(df)
    df = apply_rules(df)
    df = add_plan_rank(df)
    budget = shared.CONSTANTS["budget_rupees"]
    ranked = rank(df, budget)

    funded = ranked[ranked["within_budget"]]
    actionable = int((df["recommended_action"] != "None").sum())
    mean_drop_all = float(df["cooling_c"].mean())
    mean_drop_treated = float(
        df.loc[df["recommended_action"] != "None", "cooling_c"].mean()) if actionable else 0.0

    meta = {
        "slug": slug,
        "name": name,
        "region": region,
        "bbox": bbox,
        # Which outline the cells were clipped to, and whether the study area
        # is the whole city or a window inside it. Without this the dashboard
        # cannot tell a city from a crop of one.
        "boundary": boundary_name,
        "boundary_mode": boundary_mode,
        "cells": int(len(df)),
        "actionable_cells": actionable,
        "mean_lst_c": round(float(df["LST"].mean()), 2),
        "max_lst_c": round(float(df["LST"].max()), 2),
        "mean_ndvi": round(float(df["NDVI"].mean()), 3),
        "mean_drop_treated_c": round(mean_drop_treated, 2),
        "mean_drop_grid_c": round(mean_drop_all, 2),
        "cost_all_actionable_inr": int(df["cost_estimate"].sum()),
        "budget_inr": budget,
        "funded_cells": int(len(funded)),
        "funded_cost_inr": int(funded["cost_estimate"].sum()),
        "funded_action_mix": funded["recommended_action"].value_counts().to_dict(),
        "action_mix": df["recommended_action"].value_counts().to_dict(),
        "land_cover_mix": df["land_cover"].value_counts().to_dict(),
        "heat_risk_lst_scale": list(lst_scale),
        "heat_risk_lst_scale_basis": scale_basis,
        "tier_cut_high": round(hi_cut, 4),
        "tier_cut_low": round(lo_cut, 4),
        "cell_area_m2": round(float(df["cell_area_m2"].mean()), 1),
        "composite_window": [start, end],
        "composite_season": season_label,
        "scenes_used": int(data["_scenes_used"]),
        "max_cloud_cover_pct": args.max_cloud,
        "source": "Microsoft Planetary Computer STAC "
                  "(Landsat 8/9 C2 L2 + ESA WorldCover v200)",
        "built_by": "backend/build_city.py",
        "cost_basis_applies": bool(cost_ok),
        "cost_basis_note": (
            "Unit rates in shared/constants.json are Indian municipal INR/m2. "
            "They are applied here unchanged."
            if cost_ok else
            "Unit rates in shared/constants.json are INDIAN municipal INR/m2 and "
            "do NOT transfer to this city. Every cost figure below is the Indian "
            "rate card applied to a non-Indian city, which is wrong by an unknown "
            "factor. Treat the geometry and the temperatures as real and every "
            "rupee figure as a placeholder."
        ),
    }

    print(f"\n  {meta['cells']:,} cells, mean LST {meta['mean_lst_c']} C, "
          f"peak {meta['max_lst_c']} C")
    print(f"  {actionable:,} actionable; action mix {meta['action_mix']}")
    print(f"  budget INR {budget:,} funds {meta['funded_cells']:,} cells "
          f"({meta['funded_action_mix']})")
    if not cost_ok:
        print("  WARNING: the INR cost model does not apply to this city.")

    write_outputs(slug, meta, df, ranked, OUT_ROOT / slug)
    update_manifest()
    print()


if __name__ == "__main__":
    main()
