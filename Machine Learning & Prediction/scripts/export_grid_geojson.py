"""
Step 4 - Export grid.geojson for the dashboard.

Emits a FeatureCollection whose feature properties are EXACTLY the six keys the
existing frontend reads, and no others:

    grid_id, temperature, ndvi, priority, recommended_action, cost_estimate

Consumers of those keys (do not rename without updating both sides):
  - frontend/js/mapView.js   -> properties.temperature (heat layer + legend)
  - frontend/js/popup.js     -> all six, rendered verbatim in the popup

Column renames applied here: LST -> temperature, NDVI -> ndvi.

Geometry is the original .geo polygon carried through verbatim from the source
CSV, so no reprojection or precision loss is introduced.

Input : Results/tiered.csv
Output: Results/grid.geojson

This script deliberately does NOT touch frontend/mock_data/grid.geojson. See
README section 7 for the one-line frontend change that switches the dashboard
from mock to real data.

Run:  python scripts/export_grid_geojson.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# The frontend contract. Order is cosmetic; the key set is not.
FRONTEND_PROPERTIES = [
    "grid_id",
    "temperature",
    "ndvi",
    "priority",
    "recommended_action",
    "cost_estimate",
]

TEMPERATURE_DECIMALS = 1  # popup.js prints "${temperature}degC"
NDVI_DECIMALS = 3

MODULE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = MODULE_DIR / "Results"
INPUT_CSV = RESULTS_DIR / "tiered.csv"
OUTPUT_GEOJSON = RESULTS_DIR / "grid.geojson"


def build_feature(row: pd.Series) -> dict:
    return {
        "type": "Feature",
        "geometry": json.loads(row["geo_json"]),
        "properties": {
            "grid_id": str(row["grid_id"]),
            # LST -> temperature
            "temperature": round(float(row["LST"]), TEMPERATURE_DECIMALS),
            # NDVI -> ndvi. Still the UNCORRECTED value (SPEC_AUDIT #3); the
            # dashboard displays it as-is, so the caveat must reach the reader
            # through the module README, not silently through this field.
            "ndvi": round(float(row["NDVI"]), NDVI_DECIMALS),
            "priority": str(row["priority"]),
            "recommended_action": str(row["recommended_action"]),
            # int, because popup.js calls .toLocaleString() on it
            "cost_estimate": int(row["cost_estimate"]),
        },
    }


def validate(features: list[dict]) -> None:
    """Fail loudly rather than ship a file the dashboard cannot render."""
    if not features:
        raise ValueError("No features produced")

    expected = set(FRONTEND_PROPERTIES)
    for i, f in enumerate(features):
        keys = set(f["properties"])
        if keys != expected:
            raise ValueError(
                f"Feature {i} property mismatch.\n"
                f"  unexpected: {sorted(keys - expected)}\n"
                f"  missing:    {sorted(expected - keys)}"
            )
        if f["geometry"].get("type") != "Polygon":
            raise ValueError(f"Feature {i} geometry is not a Polygon")
        if not isinstance(f["properties"]["cost_estimate"], int):
            raise ValueError(f"Feature {i} cost_estimate must be int for toLocaleString()")


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found - run scripts/tier_and_recommend.py first."
        )
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df):,} tiered rows")

    features = [build_feature(row) for _, row in df.iterrows()]
    validate(features)
    print(f"Built and validated {len(features):,} features")

    collection = {"type": "FeatureCollection", "features": features}
    OUTPUT_GEOJSON.write_text(json.dumps(collection), encoding="utf-8")

    size_mb = OUTPUT_GEOJSON.stat().st_size / 1_048_576
    print(
        f"Wrote {OUTPUT_GEOJSON.relative_to(MODULE_DIR)} "
        f"({size_mb:.2f} MB, {len(features):,} features)"
    )
    print(f"Properties per feature: {FRONTEND_PROPERTIES}")

    temps = [f["properties"]["temperature"] for f in features]
    print(f"temperature range: {min(temps):.1f} to {max(temps):.1f} C")
    print(
        "NOTE: frontend/js/mapView.js TEMP_COLOR_SCALE buckets at 30/34/38 C. "
        "Real LST tops out near 33 C, so the top two legend bands will be "
        "unused until the scale is retuned - see README section 7."
    )
    print(
        "NOTE: this file is NOT copied into frontend/mock_data/. "
        "See README section 7 to switch the dashboard over."
    )


if __name__ == "__main__":
    main()
