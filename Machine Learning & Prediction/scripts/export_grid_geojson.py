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
  - frontend/js/dataLoader.js  -> applyIntervention() subtracts cooling_c from
                                  temperature to build the "After Intervention"
                                  map.

Column renames applied here: LST -> temperature, NDVI -> ndvi.

Geometry is the original .geo polygon carried through verbatim from the source
CSV, so no reprojection or precision loss is introduced.

Input : Results/tiered.csv
Output: ../frontend/data/grid.geojson   (the file the dashboard loads)

There is deliberately ONE output. This script used to write only Results/, and
somebody copied the file into frontend/data/ by hand - an undocumented manual
step with nothing to detect it being skipped, which is part of why the dashboard
served a stale grid for weeks. It was then briefly changed to write both, which
fixed the staleness but committed the same 3.7 MB twice.

The dashboard's copy is the real artifact, so it is the only one written.

Run:  python scripts/export_grid_geojson.py
"""

from __future__ import annotations

import json
import sys
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
MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent

sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402  (path must be set before import)

VALID_ACTIONS = shared.VALID_ACTIONS

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

RESULTS_DIR = MODULE_DIR / "Results"
INPUT_CSV = RESULTS_DIR / "tiered.csv"
# The dashboard's copy, and the only one. frontend/js/main.js loads it.
OUTPUT_GEOJSON = REPO_DIR / "frontend" / "data" / "grid.geojson"


def build_feature(row: pd.Series) -> dict:
    return {
        "type": "Feature",
        "geometry": json.loads(row["geo_json"]),
        "properties": {
            "grid_id": str(row["grid_id"]),
            # LST -> temperature
            "temperature": round(float(row["LST"]), TEMPERATURE_DECIMALS),
            # NDVI -> ndvi.
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

    OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_GEOJSON.write_text(json.dumps(collection), encoding="utf-8")

    size_mb = OUTPUT_GEOJSON.stat().st_size / 1_048_576
    print(
        f"Wrote {OUTPUT_GEOJSON.relative_to(REPO_DIR)} "
        f"({size_mb:.2f} MB, {len(features):,} features)"
    )
    print(f"Properties per feature: {FRONTEND_PROPERTIES}")

    temps = [f["properties"]["temperature"] for f in features]
    print(f"temperature range: {min(temps):.1f} to {max(temps):.1f} C")
    coolings = [f["properties"]["cooling_c"] for f in features]
    print(f"cooling range: {min(coolings):.1f} to {max(coolings):.1f} C (assumed)")
    actions = pd.Series([f["properties"]["recommended_action"] for f in features])
    print(f"action mix: {actions.value_counts().to_dict()}")
    print(
        "NOTE: frontend/js/config.js derives its colour domain from the 2nd/98th "
        "percentiles of whatever it loads, so no legend retuning is needed when "
        "this file changes."
    )


if __name__ == "__main__":
    main()
