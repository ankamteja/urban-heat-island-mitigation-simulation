"""
Step 1 - Preprocessing.

Reads the Remote Sensing module's exported grid dataset, parses the embedded
GeoJSON geometry, derives per-cell centroid Latitude/Longitude (closing gaps
#7/#8 in the Remote Sensing SPEC_AUDIT without needing a GEE re-run), and
writes a tidy table for the downstream steps.

Input : ../Remote Sensing & Data Engineering/Dataset/Guwahati_Urban_Heat_Dataset.csv
Output: Results/preprocessed.csv

Run:  python scripts/preprocess.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file, so the script runs from anywhere)
# ---------------------------------------------------------------------------
MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent
SOURCE_CSV = (
    REPO_DIR
    / "Remote Sensing & Data Engineering"
    / "Dataset"
    / "Guwahati_Urban_Heat_Dataset.csv"
)
RESULTS_DIR = MODULE_DIR / "Results"
OUTPUT_CSV = RESULTS_DIR / "preprocessed.csv"

# Heat_Risk as defined in GEE/urban_heat_analysis.js section 6:
#   Heat_Risk = unitScale(LST, 20, 34) - unitScale(NDVI, -0.2, 0.8)
LST_SCALE_MIN, LST_SCALE_MAX = 20.0, 34.0
NDVI_SCALE_MIN, NDVI_SCALE_MAX = -0.2, 0.8

DROP_COLUMNS = ["system:index", "count"]


def load_source(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Source dataset not found: {path}\n"
            "Expected the Remote Sensing & Data Engineering module's exported CSV."
        )
    df = pd.read_csv(path)
    missing = {"Heat_Risk", "LST", "NDVI", "grid_id", ".geo"} - set(df.columns)
    if missing:
        raise ValueError(f"Source CSV missing expected columns: {sorted(missing)}")
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
    # NDVI CAVEAT - READ BEFORE TRUSTING ANY OUTPUT OF THIS MODULE
    #
    # The source NDVI column is computed in GEE from *raw DN* values without
    # the Landsat C2 L2 surface-reflectance rescale (x 0.0000275 - 0.2). See
    # Remote Sensing & Data Engineering/SPEC_AUDIT.md item #3 / "Fix A".
    #
    # We do NOT correct it here, and it is not a matter of preference: the
    # correction is mathematically NON-INVERTIBLE from this CSV. NDVI_wrong
    # depends only on the DN *ratio*, while NDVI_correct depends on the DN
    # *sum* as well - and the sum is not in the exported data. Worked example,
    # three band pairs that all produce the same wrong NDVI of 0.3333:
    #
    #     nir=20000 red=10000 -> wrong 0.3333, correct 0.6471
    #     nir=40000 red=20000 -> wrong 0.3333, correct 0.4400
    #
    # Recovering true NDVI therefore requires re-running the GEE script with
    # Fix A applied and re-exporting. Until then every NDVI value below is
    # compressed toward zero, and Heat_Risk (which subtracts NDVI) is
    # correspondingly biased HIGH - vegetation is systematically
    # under-credited.
    #
    # NOTE FOR FUTURE CONTRIBUTORS: because this module applies no NDVI
    # correction, fixing item A upstream in the GEE script and re-exporting is
    # safe - there is no double-correction hazard. This pipeline simply reads
    # whatever NDVI column it is given.
    # -----------------------------------------------------------------------
    print(
        "WARNING: NDVI is passed through UNCORRECTED (raw-DN artifact, "
        "SPEC_AUDIT #3). Correction is non-invertible from this CSV - it needs "
        "a GEE re-run. Heat_Risk inherits an upward bias."
    )
    print(
        f"         NDVI observed range: {df['NDVI'].min():.3f} to "
        f"{df['NDVI'].max():.3f} (healthy vegetation should reach ~0.8)"
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
    out = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns]).rename(
        columns={".geo": "geo_json"}
    )
    out = out[
        ["grid_id", "LST", "NDVI", "Heat_Risk", "Latitude", "Longitude", "geo_json"]
    ]

    if out.isna().to_numpy().any():
        raise ValueError("Unexpected nulls after preprocessing")

    out.to_csv(OUTPUT_CSV, index=False)
    print(f"Dropped columns: {DROP_COLUMNS}")
    print(f"Wrote {len(out):,} rows -> {OUTPUT_CSV.relative_to(MODULE_DIR)}")


if __name__ == "__main__":
    main()
