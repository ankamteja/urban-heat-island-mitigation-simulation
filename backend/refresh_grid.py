"""
Re-measure the committed Guwahati grid from open satellite data.

This replaces backend/refresh_dataset.py, which does the same job through
Google Earth Engine and needs a service-account key
(EE_SERVICE_ACCOUNT_JSON) to run. That key was the only credential anywhere
in this repository, and it made the project's one automated job something a
fork could not run: no account, no refresh.

Nothing about the measurement requires Earth Engine. The same Landsat
Collection 2 Level 2 scenes are served anonymously by Microsoft Planetary
Computer, with the same USGS scaling coefficients and the same QA_PIXEL
cloud mask, so this script produces the same quantity through a path that
needs no account. Every step is imported from build_city.py rather than
reimplemented -- one composite, one set of formulas, one place to fix.

WHAT IS AND IS NOT REGENERATED

The grid is not regenerated. Cell geometry and grid_id come from the
committed dataset.csv and are written back unchanged. Only the measured
columns move: LST, NDVI, NDBI, Vegetation, LandCover, Heat_Risk, count.

grid_id is the join key for every downstream file, and a cell that changed
identity between runs would silently re-point every recommendation and every
cost. Cells are matched by grid_id and any cell the new composite cannot
measure keeps its committed values rather than being dropped, so the row set
is identical before and after.

Heat_Risk keeps the committed 20-34 degC scale rather than deriving bounds
from this composite. The refreshed file has to stay comparable with the one
it replaces; re-deriving the scale would move every Heat_Risk value and every
priority tier for reasons that have nothing to do with the temperature having
changed.

Run:
    python backend/refresh_grid.py --dry-run
    python backend/refresh_grid.py --days 365
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR / "shared"))

import build_city as bc  # noqa: E402
import uhi_shared as shared  # noqa: E402

# The scale the committed dataset was built with. See the module docstring.
COMMITTED_LST_SCALE = (20.0, 34.0)

# Columns this script is allowed to change. Everything else in dataset.csv is
# identity or geometry and is carried through untouched.
MEASURED = ["Heat_Risk", "LST", "LandCover", "NDBI", "NDVI", "Vegetation", "count"]


def load_committed() -> pd.DataFrame:
    path = shared.source_dataset_path()
    df = pd.read_csv(path)
    missing = [c for c in bc.DATASET_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"{path} is missing columns: {missing}")
    return df


def lattice_bounds(grid_ids) -> tuple[int, int, int, int]:
    """The lattice window covering the committed cells.

    Read from the ids themselves. They are indices into the global lattice --
    see docs/12-multi-city.md -- so the study area is recoverable from the
    committed file alone, with no boundary asset and no geocoder call.
    """
    cols, rows = [], []
    for gid in grid_ids:
        body = gid[1:]
        for i, ch in enumerate(body):
            if ch in "+-":
                cols.append(int(gid[: i + 1]))
                rows.append(int(body[i:]))
                break
        else:
            raise SystemExit(f"grid_id {gid!r} is not a lattice index")
    return min(cols), min(rows), max(cols) + 1, max(rows) + 1


def measure(committed: pd.DataFrame, start: str, end: str,
            max_cloud: float, max_scenes: int, season: str) -> pd.DataFrame:
    col0, row0, col1, row1 = lattice_bounds(committed["grid_id"])
    cols = np.arange(col0, col1)
    rows = np.arange(row0, row1)
    rows_desc = rows[::-1]
    shape = (len(rows), len(cols))

    bbox = [col0 * bc.CELL_SIZE_DEG, row0 * bc.CELL_SIZE_DEG,
            col1 * bc.CELL_SIZE_DEG, row1 * bc.CELL_SIZE_DEG]

    from rasterio.transform import from_origin
    transform = from_origin(col0 * bc.CELL_SIZE_DEG, row1 * bc.CELL_SIZE_DEG,
                            bc.CELL_SIZE_DEG, bc.CELL_SIZE_DEG)

    print(f"  lattice {shape[1]} x {shape[0]} covering {len(committed):,} committed cells")
    print(f"  window {start} to {end}")

    centre_lat = (bbox[1] + bbox[3]) / 2
    if season == "all":
        months = None
        print("  season filter: all months")
    else:
        months = {3, 4, 5, 6} if centre_lat >= 0 else {11, 12, 1, 2}
        print("  season filter: local hot season")

    bc.check_gdal()
    catalog = bc.open_catalog()
    items = bc.pick_scenes(catalog, bbox, start, end, max_cloud, max_scenes,
                           months=months)
    data = bc.composite_landsat(items, shape, transform)
    lc, veg = bc.worldcover(catalog, bbox, shape, transform)
    data["landcover"] = lc
    data["vegetation"] = veg

    return bc.build_dataframe(cols, rows_desc, data, COMMITTED_LST_SCALE)


def assemble(committed: pd.DataFrame, measured: pd.DataFrame) -> pd.DataFrame:
    """Committed identity and geometry, refreshed measurements."""
    new = measured.rename(columns={"obs_count": "count"})[
        ["grid_id", "LST", "NDVI", "NDBI", "Heat_Risk", "LandCover",
         "Vegetation", "count"]
    ]

    merged = committed.merge(new, on="grid_id", how="left", suffixes=("", "_new"))

    unmeasured = int(merged["LST_new"].isna().sum())
    if unmeasured:
        print(f"  {unmeasured:,} cells could not be measured in this composite "
              f"(cloud or scene edge); keeping their committed values")

    for column in MEASURED:
        fresh = merged[f"{column}_new"]
        merged[column] = fresh.where(fresh.notna(), merged[column])

    out = merged[bc.DATASET_COLUMNS].copy()
    assert len(out) == len(committed), "the refresh changed the row set"
    assert (out["grid_id"].values == committed["grid_id"].values).all(), \
        "the refresh reordered or re-pointed grid_id"
    return out


def report(old: pd.DataFrame, new: pd.DataFrame) -> None:
    print("\n  change report")
    joined = old[["grid_id", "LST", "NDVI"]].merge(
        new[["grid_id", "LST", "NDVI"]], on="grid_id", suffixes=("_old", "_new"))
    d_lst = joined["LST_new"] - joined["LST_old"]
    print(f"    mean LST  {old['LST'].mean():6.2f} -> {new['LST'].mean():6.2f} C "
          f"(mean shift {d_lst.mean():+.2f}, max |shift| {d_lst.abs().max():.2f})")
    print(f"    NDVI      {old['NDVI'].min():.3f}..{old['NDVI'].max():.3f} -> "
          f"{new['NDVI'].min():.3f}..{new['NDVI'].max():.3f}")
    moved = int((d_lst.abs() > 5).sum())
    if moved:
        print(f"    {moved:,} cells moved more than 5 C -- inspect before committing")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=365,
                    help="Length of the window ending today (default 365)")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--max-cloud", type=float, default=20.0)
    ap.add_argument("--max-scenes", type=int, default=8)
    ap.add_argument("--season", choices=["hot", "all"], default="all",
                    help="'all' matches the committed annual composite (default)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Measure and report without writing dataset.csv")
    args = ap.parse_args()

    end = args.end or date.today().isoformat()
    start = args.start or (date.fromisoformat(end) - timedelta(days=args.days)).isoformat()

    print("Refreshing the committed grid from Microsoft Planetary Computer")
    print("  no account, no API key, no credential of any kind")

    committed = load_committed()
    measured = measure(committed, start, end, args.max_cloud, args.max_scenes,
                       args.season)
    fresh = assemble(committed, measured)
    report(committed, fresh)

    if args.dry_run:
        print("\n  --dry-run: dataset.csv not written.")
        return

    path = shared.source_dataset_path()
    fresh.to_csv(path, index=False)
    print(f"\n  wrote {path.relative_to(REPO_DIR)} ({len(fresh):,} rows)")


if __name__ == "__main__":
    main()
