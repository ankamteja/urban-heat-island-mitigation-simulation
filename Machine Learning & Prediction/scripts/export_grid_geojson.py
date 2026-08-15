"""
Step 4 - Export grid.geojson for the dashboard.

Emits a FeatureCollection whose feature properties are EXACTLY the ten keys
the existing frontend reads, and no others:

    grid_id, temperature, ndvi, ndbi, land_cover, priority, recommended_action,
    exclusion_reason, cost_estimate, cooling_c

Consumers of those keys (do not rename without updating both sides):
  - frontend/js/mapView.js     -> properties.temperature (heat layer + legend)
  - frontend/js/inspector.js   -> grid_id, temperature, ndvi, ndbi, land_cover,
                                  priority, recommended_action,
                                  exclusion_reason, cost_estimate
  - frontend/js/dataLoader.js  -> applyIntervention() subtracts cooling_c from
                                  temperature to build the mitigation surface.

ndbi, land_cover and exclusion_reason were added for the cell inspector: it has
to answer "why this cell?", and that answer is land cover plus built-up
intensity for a treated cell, or the exclusion reason for an untreated one.
Deriving any of it in the browser would mean re-implementing the rule engine on
the client, which is exactly the duplication this contract exists to prevent.

Column renames applied here: LST -> temperature, NDVI -> ndvi, NDBI -> ndbi.

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
from hashlib import sha256
from pathlib import Path

import pandas as pd

# The frontend contract. Order is cosmetic; the key set is not.
FRONTEND_PROPERTIES = [
    "grid_id",
    "temperature",
    "ndvi",
    "ndbi",
    "land_cover",
    "priority",
    "recommended_action",
    "exclusion_reason",
    "cost_estimate",
    "cooling_c",
    "plan_rank",
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
# A tiny manifest is written with the grid. The browser fetches it without a
# cache, then requests the grid under its content hash. This makes a new Vercel
# deployment visibly and mechanically different from a stale grid response.
OUTPUT_RELEASE = REPO_DIR / "frontend" / "data" / "release.json"


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
            # NDBI -> ndbi. The inspector labels this "built-up intensity"; it is
            # the strongest single driver in the model (0.408 importance), so it
            # is the honest answer to "why is this cell hot?".
            "ndbi": round(float(row["NDBI"]), NDVI_DECIMALS),
            # Already normalised by add_land_cover(); the raw WorldCover integer
            # would mean nothing in a UI.
            "land_cover": str(row["land_cover"]),
            "priority": str(row["priority"]),
            "recommended_action": str(row["recommended_action"]),
            # Empty for the 4,157 actionable cells - pandas reads the blank as
            # NaN, and "nan" in a UI is the same defect STRING_COLUMNS exists to
            # prevent. Normalised to "" so the frontend can branch on falsiness.
            "exclusion_reason": (
                "" if pd.isna(row["exclusion_reason"]) else str(row["exclusion_reason"])
            ),
            # int, because popup.js calls .toLocaleString() on it
            "cost_estimate": int(row["cost_estimate"]),
            # float, because compareView.js computes temperature - cooling_c.
            # This is an ASSUMED cooling, not a predicted one - see Rule 5 in
            # tier_and_recommend.py.
            "cooling_c": round(float(row["cooling_c"]), COOLING_DECIMALS),
            # The pipeline's funding order. 0 for cells that are never funded.
            # int, because the browser sorts on it.
            "plan_rank": int(row["plan_rank"]),
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


def add_plan_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Carry the funding order into the grid, so the browser never re-derives it.

    The dashboard lets a planner re-run the budget over a filtered subset, which
    means it needs the priority order client-side. Deriving it in JavaScript from
    the exported fields does not work: `temperature` ships at 1 dp because that is
    what the UI prints, cooling_per_rupee has only three distinct values, and
    thousands of cells therefore tie at a precision the pipeline never saw. Sorted
    that way the browser funded 249 cells that cost the same and cooled the same
    as the pipeline's 249 - and were an entirely different 249.

    So the rank is computed once, here, at full precision, using the same keys as
    rank_within_budget() in member3_decision_support.py. The browser sorts on this
    integer and nothing else, which makes disagreement with ranking.csv
    structurally impossible rather than merely unlikely.

    Non-actionable cells get 0: they are never funded at any budget.
    """
    df = df.copy()
    actionable = df["recommended_action"] != "None"

    ranked = df[actionable].copy()

    # Cooling per rupee is an ATTRIBUTE OF THE MEASURE, not of the cell, and it
    # has to be computed that way or it stops working as a sort key.
    #
    # This module prices each cell from its own polygon area, so cost_estimate
    # varies by a few rupees between cells with the same action (401327, 401331,
    # ...) where Decision-Support uses one flat area (401310). Dividing per cell
    # turns that geometric noise into ~3,500 distinct scores differing in the
    # sixth decimal, which then dominate the sort and leave LST unused: the first
    # attempt ranked a 25.1 C cell above a 33.2 C one because its polygon was a
    # few square metres smaller.
    #
    # Using the median cost per action restores the three real values - one per
    # measure, the thing the ratio is actually comparing - so the LST tie-break
    # decides which cells get funded, exactly as it does in the pipeline.
    unit_cost = ranked.groupby("recommended_action")["cost_estimate"].transform("median")
    ranked["_cpr"] = ranked["cooling_c"] / unit_cost
    ranked = ranked.sort_values(
        ["_cpr", "LST", "grid_id"],
        ascending=[False, False, True],
        kind="mergesort",
    )

    df["plan_rank"] = 0
    df.loc[ranked.index, "plan_rank"] = range(1, len(ranked) + 1)
    print(f"Ranked {len(ranked):,} actionable cells for the plan order")
    return df


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

    df = add_plan_rank(df)

    features = [build_feature(row) for _, row in df.iterrows()]
    validate(features)
    print(f"Built and validated {len(features):,} features")

    collection = {"type": "FeatureCollection", "features": features}
    payload = json.dumps(collection, separators=(",", ":")).encode("utf-8")
    grid_sha256 = sha256(payload).hexdigest()
    actions = pd.Series([f["properties"]["recommended_action"] for f in features])
    release = {
        "schema_version": 1,
        "grid_sha256": grid_sha256,
        "release_id": grid_sha256[:12],
        "cell_count": len(features),
        "total_cost_inr": int(sum(f["properties"]["cost_estimate"] for f in features)),
        "action_counts": {str(k): int(v) for k, v in actions.value_counts().items()},
    }

    OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_GEOJSON.write_bytes(payload)
    OUTPUT_RELEASE.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")

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
    print(f"action mix: {actions.value_counts().to_dict()}")
    print(f"Dashboard release: {release['release_id']} ({OUTPUT_RELEASE.relative_to(REPO_DIR)})")
    print(
        "NOTE: frontend/js/config.js derives its colour domain from the 2nd/98th "
        "percentiles of whatever it loads, so no legend retuning is needed when "
        "this file changes."
    )


if __name__ == "__main__":
    main()
