"""
Step 4 - Export grid.geojson for the dashboard.

Emits a FeatureCollection whose feature properties are EXACTLY the seven keys
the existing frontend reads, and no others:

    grid_id, temperature, ndvi, priority, recommended_action, cost_estimate,
    cooling_c

Consumers of those keys (do not rename without updating both sides):
  - frontend/js/mapView.js     -> properties.temperature (heat layer + legend)
  - frontend/js/popup.js       -> grid_id, temperature, ndvi, priority,
                                  recommended_action, cost_estimate, rendered
                                  verbatim in the popup
  - frontend/js/compareView.js -> applyIntervention() subtracts cooling_c from
                                  temperature to build the "After Intervention"
                                  map. It falls back to a flat 3 C only for
                                  features carrying no cooling_c, which means
                                  the legacy mock_data/grid.geojson and nothing
                                  this script produces.

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
    "cooling_c",
]

TEMPERATURE_DECIMALS = 1  # popup.js prints "${temperature}degC"
NDVI_DECIMALS = 3
# 1 dp to match TEMPERATURE_DECIMALS: compareView.js computes
# temperature - cooling_c and re-rounds to 1 dp, so a finer cooling figure
# would be discarded there anyway. Rounding here keeps the exported number and
# the displayed number identical, and it does not overstate a value that is a
# borrowed placeholder to begin with (see Rule 5 in tier_and_recommend.py -
# the degrees C come from the Decision-Support catalogue's self-declared
# "placeholder engineering estimates", not from measurement).
COOLING_DECIMALS = 1

# The four values Rule 3 of tier_and_recommend.py can emit. Listed here because
# the frontend branches on them by exact string: compareView.js skips a cell
# when recommended_action === 'None', and filters.js/popup.js render them
# verbatim. A typo or a mangled value does not crash anything - it silently
# changes which cells get an intervention applied.
VALID_ACTIONS = frozenset({"Tree cover", "Cool roof", "Green park", "None"})

# pandas reads the bare string "None" as NaN by default, because "None" is in
# its default na_values list. tiered.csv stores "None" as a real action label
# for the 2,036 low-priority cells that need no intervention, so the default
# turns them into NaN and str() then renders them as the string "nan".
#
# That is not cosmetic. compareView.js tests `action !== 'None'`; "nan" passes
# that test, so every one of those 2,036 cells was having a cooling subtraction
# applied on the "After Intervention" map despite being explicitly marked as
# needing no action - and the popup showed "Suggested: nan". The previously
# committed grid.geojson has this defect.
#
# Restricting keep_default_na to this one column fixes it without disturbing
# how the numeric columns parse.
STRING_COLUMNS = ["grid_id", "priority", "recommended_action"]

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
            # float, because compareView.js computes temperature - cooling_c.
            # This is an ASSUMED cooling, not a predicted one - see Rule 5 in
            # tier_and_recommend.py.
            "cooling_c": round(float(row["cooling_c"]), COOLING_DECIMALS),
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
        # Same class of check as cost_estimate above. compareView.js computes
        # temperature - cooling_c; if cooling_c ships as a string the frontend
        # does string coercion rather than arithmetic, and the "After
        # Intervention" map silently renders nonsense instead of failing. The
        # numeric type is part of the contract, not a nicety.
        if not isinstance(f["properties"]["cooling_c"], (int, float)):
            raise ValueError(
                f"Feature {i} cooling_c must be numeric for temperature - cooling_c"
            )
        # Catches the "nan" defect described at STRING_COLUMNS, and any future
        # divergence between Rule 3's action table and what the frontend
        # branches on. A wrong label here is silent in the browser.
        action = f["properties"]["recommended_action"]
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"Feature {i} recommended_action {action!r} is not one of "
                f"{sorted(VALID_ACTIONS)}"
            )


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found - run scripts/tier_and_recommend.py first."
        )
    df = pd.read_csv(
        INPUT_CSV,
        # See STRING_COLUMNS: without this, the action label "None" is read as
        # NaN and exported as the string "nan".
        keep_default_na=False,
        na_values={c: [] for c in STRING_COLUMNS},
    )
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
    coolings = [f["properties"]["cooling_c"] for f in features]
    print(f"cooling range: {min(coolings):.1f} to {max(coolings):.1f} C (assumed)")
    print(
        "NOTE: frontend/js/mapView.js TEMP_COLOR_SCALE buckets at 24/27/30 C, "
        "retuned to this dataset's real LST range - all four legend bands are "
        "now exercised. See README section 7."
    )
    print(
        "NOTE: this file is NOT copied into frontend/mock_data/. "
        "See README section 7 to switch the dashboard over."
    )


if __name__ == "__main__":
    main()
