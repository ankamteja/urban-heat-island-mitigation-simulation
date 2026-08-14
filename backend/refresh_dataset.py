"""
Automated refresh of the grid dataset from Google Earth Engine.

WHAT THIS REPLACES
------------------
`Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js` runs interactively
in the Earth Engine Code Editor and exports to the operator's Google Drive. That
is fine for exploratory work and impossible to automate: it needs a human to
press Run and then move a file out of Drive and into the repository. The result
was a dashboard serving a snapshot nobody remembered to refresh.

This script does the same measurement work headlessly, against a service
account, and writes `dataset.csv` in place. A scheduled GitHub Action runs it,
re-runs the Python pipeline, and commits the result; Vercel redeploys on the
push. Nobody has to remember anything.

THE ONE IMPORTANT DIFFERENCE: THE GRID IS NOT REGENERATED
---------------------------------------------------------
The Code Editor script builds its grid with

    ee.Image.random().multiply(100000).toInt().reduceToVectors({scale: 100, ...})

and takes `grid_id` from the resulting feature ids. Those ids are a function of
how the vectoriser happens to segment the raster, so a regenerated grid can
carry different ids -- and `grid_id` is the join key for every downstream file,
the frontend contract, and the test suite.

So this script does NOT regenerate the grid. It reads the existing cell
polygons and their ids straight out of the committed `dataset.csv` and
recomputes the measured bands over exactly those geometries. Cell count, cell
ids and cell shapes are therefore stable across every refresh, by construction,
and only the measurements change. That is what makes an automated refresh safe
to run unattended.

MEASUREMENTS (identical formulas to the Code Editor script)
-----------------------------------------------------------
  LST         ST_B10 * 0.00341802 + 149.0 - 273.15          (Kelvin -> Celsius)
  SR          SR_B4/B5/B6 * 0.0000275 - 0.2                 (C2 L2 rescale)
  NDVI        normalizedDifference(SR_B5, SR_B4)
  NDBI        normalizedDifference(SR_B6, SR_B5)
  LandCover   ESA WorldCover v200, mode over the cell
  Vegetation  WorldCover classes 10/20/30/40 -> 1 else 0, mean over the cell
  Heat_Risk   unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)

Cloud handling is also identical: scene-level CLOUD_COVER < 20, plus a per-pixel
QA_PIXEL mask for dilated cloud, cirrus, cloud and cloud shadow, then a median
composite over the date window.

AUTHENTICATION
--------------
Needs a Google Cloud service account that has been registered with Earth Engine.
Provide its JSON key in the EE_SERVICE_ACCOUNT_JSON environment variable (the
whole JSON document, not a path). See docs/09-automated-refresh.md for the
one-time setup. This script never writes the credential anywhere.

Run:  python backend/refresh_dataset.py [--days 365] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402

# Earth Engine caps how much it will return in one synchronous call. 8,144 cells
# of reduceRegions in a single request reliably exceeds it, so the work is
# chunked. 400 is comfortably inside the limit and keeps the number of round
# trips reasonable.
CHUNK_SIZE = 400

# Scene selection, matching the Code Editor script.
MAX_SCENE_CLOUD_COVER = 20
LANDSAT_COLLECTION = "LANDSAT/LC08/C02/T1_L2"
WORLDCOVER_COLLECTION = "ESA/WorldCover/v200"

# Heat_Risk scaling bounds. These MUST match preprocess.py's
# verify_heat_risk_identity(), which asserts the relationship holds to ~1e-15.
LST_SCALE_MIN, LST_SCALE_MAX = 20.0, 34.0
NDVI_SCALE_MIN, NDVI_SCALE_MAX = -0.2, 0.8

VEGETATED_CLASSES = [10, 20, 30, 40]

OUTPUT_COLUMNS = [
    "system:index", "Heat_Risk", "LST", "LandCover", "Latitude", "Longitude",
    "NDBI", "NDVI", "Vegetation", "count", "grid_id", ".geo",
]


def authenticate() -> None:
    """Initialise Earth Engine from a service-account key in the environment."""
    # Checked before importing ee, so a missing credential reports the thing the
    # operator can actually fix rather than an import error behind it.
    raw = os.environ.get("EE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise SystemExit(
            "EE_SERVICE_ACCOUNT_JSON is not set.\n"
            "It must contain the full JSON key of a Google Cloud service account "
            "registered with Earth Engine. See docs/09-automated-refresh.md."
        )

    try:
        import ee
    except ImportError as exc:
        raise SystemExit(
            "The earthengine-api package is not installed.\n"
            "    pip install earthengine-api"
        ) from exc

    try:
        key = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"EE_SERVICE_ACCOUNT_JSON is not valid JSON: {exc}") from exc

    email = key.get("client_email")
    if not email:
        raise SystemExit("Service-account JSON has no client_email field.")

    # The EE client wants a file path, so the key is written to a private temp
    # file and removed immediately after initialisation.
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    try:
        handle.write(raw)
        handle.close()
        os.chmod(handle.name, 0o600)
        credentials = ee.ServiceAccountCredentials(email, handle.name)
        ee.Initialize(credentials)
    finally:
        os.unlink(handle.name)

    print(f"Earth Engine authenticated as {email}")


def load_existing_cells(path: Path) -> pd.DataFrame:
    """
    Read the committed grid: ids and geometry only.

    This is the load-bearing decision described in the module docstring. The
    geometry column is carried through verbatim so the refreshed dataset has
    byte-identical cell polygons and the join key never moves.
    """
    df = pd.read_csv(path)
    for column in ("grid_id", ".geo"):
        if column not in df.columns:
            raise SystemExit(f"{path.name} has no {column!r} column.")
    print(f"Loaded {len(df):,} existing grid cells from {path.name}")
    return df


def build_imagery(start: str, end: str):
    """Median composite plus the derived bands, over the given date window."""
    import ee

    def mask_clouds(img):
        qa = img.select("QA_PIXEL")
        mask = (
            qa.bitwiseAnd(1 << 1).eq(0)      # dilated cloud
            .And(qa.bitwiseAnd(1 << 2).eq(0))  # cirrus
            .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
            .And(qa.bitwiseAnd(1 << 4).eq(0))  # cloud shadow
        )
        return img.updateMask(mask)

    collection = (
        ee.ImageCollection(LANDSAT_COLLECTION)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", MAX_SCENE_CLOUD_COVER))
    )

    scene_count = collection.size().getInfo()
    if scene_count == 0:
        raise SystemExit(
            f"No Landsat scenes between {start} and {end} under "
            f"{MAX_SCENE_CLOUD_COVER}% cloud. Widen the window with --days."
        )
    print(f"{scene_count} scenes in window {start} to {end}")

    image = collection.map(mask_clouds).median()

    lst = (
        image.select("ST_B10")
        .multiply(0.00341802).add(149.0).subtract(273.15)
        .rename("LST")
    )
    sr = image.select(["SR_B4", "SR_B5", "SR_B6"]).multiply(0.0000275).add(-0.2)
    ndvi = sr.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")
    ndbi = sr.normalizedDifference(["SR_B6", "SR_B5"]).rename("NDBI")

    worldcover = (
        ee.ImageCollection(WORLDCOVER_COLLECTION).first()
        .select("Map").rename("LandCover")
    )
    vegetation = worldcover.remap(
        VEGETATED_CLASSES, [1] * len(VEGETATED_CLASSES), 0
    ).rename("Vegetation")

    return lst, ndvi, ndbi, worldcover, vegetation


def measure(cells: pd.DataFrame, bands) -> pd.DataFrame:
    """
    Reduce every band over every committed cell polygon, in chunks.

    LandCover uses mode because it is categorical; everything else uses mean.
    """
    import ee

    lst, ndvi, ndbi, worldcover, vegetation = bands
    continuous = lst.addBands(ndvi).addBands(ndbi).addBands(vegetation)

    rows: list[dict] = []
    total = len(cells)

    for start in range(0, total, CHUNK_SIZE):
        chunk = cells.iloc[start:start + CHUNK_SIZE]
        features = [
            ee.Feature(ee.Geometry(json.loads(geo)), {"grid_id": str(gid)})
            for gid, geo in zip(chunk["grid_id"], chunk[".geo"], strict=True)
        ]
        fc = ee.FeatureCollection(features)

        means = continuous.reduceRegions(
            collection=fc, reducer=ee.Reducer.mean(), scale=30
        )
        modes = worldcover.reduceRegions(
            collection=means, reducer=ee.Reducer.mode(), scale=30
        )

        for feature in modes.getInfo()["features"]:
            props = feature["properties"]
            rows.append(
                {
                    "grid_id": props["grid_id"],
                    "LST": props.get("LST"),
                    "NDVI": props.get("NDVI"),
                    "NDBI": props.get("NDBI"),
                    "Vegetation": props.get("Vegetation"),
                    "LandCover": props.get("mode"),
                }
            )

        done = min(start + CHUNK_SIZE, total)
        print(f"  measured {done:,}/{total:,} cells", flush=True)

    return pd.DataFrame(rows)


def assemble(cells: pd.DataFrame, measured: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the dataset in the exact schema the pipeline expects."""
    original = cells.copy()
    original["grid_id"] = original["grid_id"].astype(str)
    measured["grid_id"] = measured["grid_id"].astype(str)

    merged = original[["grid_id", ".geo"]].merge(measured, on="grid_id", how="left")
    if len(merged) != len(original):
        raise SystemExit("Row count changed while merging measurements.")

    missing = merged[["LST", "NDVI", "NDBI", "LandCover", "Vegetation"]].isna().any(axis=1)
    if missing.any():
        # Cells fully masked by cloud in every scene produce no value. Refusing
        # here is deliberate: a partially-null dataset would silently propagate
        # NaN through the whole pipeline.
        raise SystemExit(
            f"{int(missing.sum())} cells have no measurement (likely cloud-masked "
            "in every scene in the window). Widen the window with --days."
        )

    # Centroids, so the dataset carries the same Latitude/Longitude columns.
    from shapely.geometry import shape

    geometries = [shape(json.loads(g)) for g in merged[".geo"]]
    merged["Longitude"] = [g.centroid.x for g in geometries]
    merged["Latitude"] = [g.centroid.y for g in geometries]

    merged["Heat_Risk"] = (
        (merged["LST"] - LST_SCALE_MIN) / (LST_SCALE_MAX - LST_SCALE_MIN)
        - (merged["NDVI"] - NDVI_SCALE_MIN) / (NDVI_SCALE_MAX - NDVI_SCALE_MIN)
    )

    merged["system:index"] = [f"{i:08d}" for i in range(len(merged))]
    merged["count"] = 1

    return merged[OUTPUT_COLUMNS]


def report_change(old: pd.DataFrame, new: pd.DataFrame) -> None:
    """Print what actually moved, so a scheduled run is auditable from its log."""
    joined = old[["grid_id", "LST", "NDVI"]].astype({"grid_id": str}).merge(
        new[["grid_id", "LST", "NDVI"]].astype({"grid_id": str}),
        on="grid_id", suffixes=("_old", "_new"),
    )
    lst_delta = (joined["LST_new"] - joined["LST_old"])
    print(
        f"\nLST change: mean {lst_delta.mean():+.3f} C, "
        f"max {lst_delta.abs().max():.3f} C"
    )
    print(
        f"NDVI range: {new['NDVI'].min():.3f} to {new['NDVI'].max():.3f} "
        f"(was {old['NDVI'].min():.3f} to {old['NDVI'].max():.3f})"
    )
    if not shared.ndvi_looks_corrected(float(new["NDVI"].max())):
        raise SystemExit(
            "Refreshed NDVI looks uncorrected -- refusing to write. The "
            "surface-reflectance rescale is missing from build_imagery()."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=365,
        help="Length of the date window ending today (default: 365). Landsat 8 "
             "revisits every ~16 days, so a window shorter than about 30 days "
             "may contain no usable scene.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Measure and report, but do not write dataset.csv.",
    )
    args = parser.parse_args()

    dataset_path = shared.source_dataset_path()
    cells = load_existing_cells(dataset_path)

    end = date.today()
    start = end - timedelta(days=args.days)

    authenticate()
    bands = build_imagery(start.isoformat(), end.isoformat())

    print(f"Measuring {len(cells):,} cells in chunks of {CHUNK_SIZE}...")
    measured = measure(cells, bands)
    refreshed = assemble(cells, measured)
    report_change(cells, refreshed)

    if args.dry_run:
        print("\n--dry-run: dataset.csv not written.")
        return

    refreshed.to_csv(dataset_path, index=False)
    print(f"\nWrote {len(refreshed):,} rows -> {dataset_path.name}")
    print(
        "Next: re-run the ML pipeline and Decision-Support so the derived "
        "products match. The refresh workflow does this automatically."
    )


if __name__ == "__main__":
    main()
