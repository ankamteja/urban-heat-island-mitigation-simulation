"""
Step 1 - Preprocessing.

Reads the Remote Sensing module's exported grid dataset, parses the embedded
GeoJSON geometry, derives per-cell centroid Latitude/Longitude (closing gaps
#7/#8 in the Remote Sensing SPEC_AUDIT without needing a GEE re-run), and
writes a tidy table for the downstream steps.

Input : ../Remote Sensing & Data Engineering/Dataset/dataset.csv
Output: Results/preprocessed.csv

Run:  python scripts/preprocess.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file, so the script runs from anywhere)
# ---------------------------------------------------------------------------
MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent

sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402  (path must be set before import)

# Resolved through the shared helper rather than hardcoded here. The dataset
# was renamed once (Guwahati_Urban_Heat_Dataset.csv -> dataset.csv) and both
# this module and Decision-Support kept the old name, so both crashed on a
# clean clone. One definition now, in shared/constants.json.
SOURCE_CSV = shared.source_dataset_path()
RESULTS_DIR = MODULE_DIR / "Results"
OUTPUT_CSV = RESULTS_DIR / "preprocessed.csv"

# Heat_Risk as defined in GEE/urban_heat_analysis.js section 6:
#   Heat_Risk = unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)
LST_SCALE_MIN, LST_SCALE_MAX = 20.0, 34.0
NDVI_SCALE_MIN, NDVI_SCALE_MAX = -0.2, 0.8

DROP_COLUMNS = ["system:index", "count"]


# Columns the corrected Earth Engine export added. LandCover is not optional:
# without it the downstream rule engine has no way to tell a lake from a car
# park, and it previously recommended planting trees on open water. NDBI and
# Vegetation are carried because they are the two strongest predictors of LST
# in this dataset (NDBI +0.61, Vegetation -0.46, versus NDVI -0.40).
REQUIRED_COLUMNS = {
    "Heat_Risk", "LST", "NDVI", "grid_id", ".geo",
    "LandCover", "NDBI", "Vegetation",
}


def load_source(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Source dataset not found: {path}\n"
            "Expected the Remote Sensing & Data Engineering module's exported CSV."
        )
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Source CSV missing expected columns: {sorted(missing)}\n"
            "LandCover / NDBI / Vegetation come from the corrected Earth Engine "
            "export. If they are absent you are reading the pre-fix dataset; "
            "re-run Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js."
        )
    return df


def parse_geometry(geo_json_strings: pd.Series) -> list:
    """Parse the .geo column (GeoJSON polygon strings) into shapely geometries."""
    return [shape(json.loads(s)) for s in geo_json_strings]


def add_centroids(df: pd.DataFrame, geometries: list) -> pd.DataFrame:
    """Derive scalar Latitude/Longitude from each cell's polygon centroid."""
    centroids = [g.centroid for g in geometries]
    df["Longitude"] = [c.x for c in centroids]
    df["Latitude"] = [c.y for c in centroids]
    return df


def verify_heat_risk_identity(df: pd.DataFrame) -> float:
    """
    Heat_Risk is not an independent measurement - it is a closed-form function
    of LST and NDVI. Confirming that here is what justifies using LST (not
    Heat_Risk) as the regression target in step 2; see README section 3.
    """
    expected = (df["LST"] - LST_SCALE_MIN) / (LST_SCALE_MAX - LST_SCALE_MIN) - (
        df["NDVI"] - NDVI_SCALE_MIN
    ) / (NDVI_SCALE_MAX - NDVI_SCALE_MIN)
    return float(np.abs(df["Heat_Risk"] - expected).max())


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_source(SOURCE_CSV)
    print(f"Loaded {len(df):,} rows from {SOURCE_CSV.name}")

    # -----------------------------------------------------------------------
    # NDVI PROVENANCE CHECK
    #
    # An earlier Earth Engine script computed NDVI from *raw DN* values without
    # the Landsat C2 L2 surface-reflectance rescale (x 0.0000275 - 0.2), which
    # compressed the whole city below ~0.39 and biased Heat_Risk high, since
    # Heat_Risk subtracts NDVI. That correction is NOT recoverable from the
    # exported CSV - NDVI_wrong depends only on the DN ratio while NDVI_correct
    # depends on the DN sum, and the sum is not exported. It needs a GEE re-run.
    #
    # That re-run has since happened. Rather than hardcode a caveat about the
    # data - which is how every script in this repo ended up printing
    # "NDVI is UNCORRECTED" for weeks after the corrected export landed - the
    # warning is now DERIVED from the data actually in hand.
    # -----------------------------------------------------------------------
    ndvi_min, ndvi_max = float(df["NDVI"].min()), float(df["NDVI"].max())
    if shared.ndvi_looks_corrected(ndvi_max):
        print(
            f"NDVI range {ndvi_min:.3f} to {ndvi_max:.3f} - consistent with the "
            "corrected (surface-reflectance) export."
        )
    else:
        print(
            f"WARNING: NDVI range {ndvi_min:.3f} to {ndvi_max:.3f} - too "
            "compressed to be surface reflectance. This looks like the pre-fix "
            "raw-DN export; Heat_Risk inherits an upward bias and every tier "
            "below is suspect. Re-run the GEE script and re-export."
        )

    geometries = parse_geometry(df[".geo"])
    print(f"Parsed {len(geometries):,} polygon geometries from the .geo column")

    df = add_centroids(df, geometries)
    print(
        f"Derived centroids: lon {df['Longitude'].min():.5f} to "
        f"{df['Longitude'].max():.5f}, lat {df['Latitude'].min():.5f} to "
        f"{df['Latitude'].max():.5f}"
    )

    residual = verify_heat_risk_identity(df)
    print(f"Heat_Risk identity check: max |actual - f(LST, NDVI)| = {residual:.2e}")
    if residual < 1e-9:
        print(
            "         -> Heat_Risk is deterministic in LST and NDVI. "
            "Regression target is LST (see README section 3)."
        )

    # Keep the original .geo string verbatim so the export step reproduces the
    # source polygons exactly rather than round-tripping through a reprojection.
    # Human-readable land-cover label alongside the raw WorldCover code, so
    # every downstream file is auditable without a lookup table to hand.
    df["land_cover"] = df["LandCover"].map(shared.land_cover_label)
    print("\nLand cover distribution:")
    print(df["land_cover"].value_counts().to_string())

    out = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns]).rename(
        columns={".geo": "geo_json"}
    )
    # LandCover / NDBI / Vegetation are carried forward from here on. They were
    # previously dropped at this exact line, which is why the rule engine had no
    # land-cover input and recommended tree planting on open water.
    out = out[
        [
            "grid_id", "LST", "NDVI", "Heat_Risk",
            "LandCover", "land_cover", "NDBI", "Vegetation",
            "Latitude", "Longitude", "geo_json",
        ]
    ]

    if out.isna().to_numpy().any():
        raise ValueError("Unexpected nulls after preprocessing")

    out.to_csv(OUTPUT_CSV, index=False)
    print(f"Dropped columns: {DROP_COLUMNS}")
    print(f"Wrote {len(out):,} rows -> {OUTPUT_CSV.relative_to(MODULE_DIR)}")


if __name__ == "__main__":
    main()
