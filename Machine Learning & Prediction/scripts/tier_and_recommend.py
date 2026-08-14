"""
Step 3 - Priority tiering and mitigation recommendations.

There is no labelled ground truth anywhere in this project for "priority" or
"recommended action", so this step is deliberately NOT a supervised classifier
pretending to have learned them. It is an explicit, auditable rule engine over
Heat_Risk and NDVI. Every threshold and unit cost is a named constant below and
is reproduced in README sections 4 and 5.

Input : Results/preprocessed.csv
Output: Results/tiered.csv
        Results/priority_map.png
        Results/tiering_summary.md

Run:  python scripts/tier_and_recommend.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import shape

MODULE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = MODULE_DIR.parent

sys.path.insert(0, str(REPO_DIR / "shared"))
import uhi_shared as shared  # noqa: E402  (path must be set before import)

# ---------------------------------------------------------------------------
# Rule 1 - priority tiers: quantile bins on Heat_Risk.
#
# Quantiles rather than absolute Heat_Risk cutoffs, because Heat_Risk is a
# unit-scaled composite whose absolute value carries no physical meaning across
# cities. Quantiles keep the tiers as relative ranks within Guwahati, which is
# what a municipal prioritisation actually needs.
#
# Cut points live in shared/constants.json so this module and Decision-Support
# tier identically - they previously computed the same quartiles from two
# separate hardcoded copies.
# ---------------------------------------------------------------------------
HIGH_QUANTILE = shared.TIERING["high_quantile"]
LOW_QUANTILE = shared.TIERING["low_quantile"]
#                      the middle 50% -> Medium

# ---------------------------------------------------------------------------
# Rule 2 - vegetation class (reported, not decisive).
#
# This used to split at the dataset MEDIAN, as a deliberate workaround: the
# pre-fix export's NDVI had a p95 of only ~0.295, so the literature threshold
# of 0.3 would have labelled the entire city "sparse" and collapsed the
# decision table.
#
# The corrected export reaches NDVI 0.78, so that workaround is retired and the
# absolute literature threshold is back (IMPROVEMENTS.md P0 item 2). Note the
# median is now ~0.45 - continuing to split there would have mislabelled every
# genuinely vegetated cell in the 0.30-0.45 band as sparse.
#
# vegetation_class is now DESCRIPTIVE only. Since the corrected export carries
# real ESA WorldCover land cover, suitability is decided by land cover (Rule 3)
# rather than inferred from a vegetation index.
# ---------------------------------------------------------------------------
VEGETATION_NDVI_THRESHOLD = shared.TIERING["vegetation_ndvi_threshold"]

# ---------------------------------------------------------------------------
# Rule 3 - action assignment, by LAND COVER and priority.
#
# This module previously keyed its action table on (priority, vegetation_class)
# with no land-cover input at all, because land cover did not exist upstream
# when it was written. The corrected export added it, but this module kept
# dropping the column in preprocess.py - so the deployed dashboard recommended
# planting trees on 148 water and wetland cells and building parks on 3,433
# built-up cells.
#
# The Decision-Support module already had the correct suitability rule. Rather
# than maintain a second copy here, both modules now call the same function.
# See shared/uhi_shared.py:assign_action for the rule and its ordering.
#
# Action names remain a hard contract with the dashboard: frontend/js/config.js
# keys INTERVENTIONS on these exact four strings.
# ---------------------------------------------------------------------------
assign_action = shared.assign_action

# ---------------------------------------------------------------------------
# Rules 4 and 5 - cost and expected cooling.
#
# Both now live in shared/constants.json, read by this module and by
# Decision-Support. THEY REMAIN PLANNING PLACEHOLDERS, NOT PROCURED COSTS OR
# MEASURED COOLING. The cooling figures in particular are not this module's
# own: they originate in the Decision-Support catalogue, whose own comment
# calls them "placeholder engineering estimates for a hackathon demo". Nothing
# is fitted to Guwahati LST, validated against a field trial, or adjusted for
# canopy age, albedo, humidity or wind, and a flat per-action number ignores
# that cooling scales with treated area and with how hot a cell already is.
#
# Replace with measured or modelled values before any figure here is quoted as
# an outcome or informs a budget.
# ---------------------------------------------------------------------------

# Degrees -> metres for cell area. The .geo polygons are axis-aligned
# rectangles in EPSG:4326, so a local equirectangular conversion is exact for
# their width/height (see Remote Sensing SPEC_AUDIT item #6: ~89.8 m x 99.3 m).
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON_EQUATOR = 111_320.0

RESULTS_DIR = MODULE_DIR / "Results"
INPUT_CSV = RESULTS_DIR / "preprocessed.csv"
OUTPUT_CSV = RESULTS_DIR / "tiered.csv"


def cell_area_m2(geo_json_str: str) -> float:
    """Metric area of one grid cell, from its polygon bounds."""
    poly = shape(json.loads(geo_json_str))
    min_x, min_y, max_x, max_y = poly.bounds
    mid_lat_rad = np.radians((min_y + max_y) / 2.0)
    width_m = (max_x - min_x) * M_PER_DEG_LON_EQUATOR * np.cos(mid_lat_rad)
    height_m = (max_y - min_y) * M_PER_DEG_LAT
    return float(width_m * height_m)


def assign_priority(heat_risk: pd.Series) -> tuple[pd.Series, float, float]:
    low_cut = float(heat_risk.quantile(LOW_QUANTILE))
    high_cut = float(heat_risk.quantile(HIGH_QUANTILE))
    priority = pd.Series("Medium", index=heat_risk.index, dtype="object")
    priority[heat_risk >= high_cut] = "High"
    priority[heat_risk <= low_cut] = "Low"
    return priority, low_cut, high_cut


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found - run scripts/preprocess.py first."
        )
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df):,} preprocessed rows")

    if "land_cover" not in df.columns:
        raise ValueError(
            "preprocessed.csv has no land_cover column - it was produced by an "
            "older preprocess.py that dropped it. Re-run scripts/preprocess.py."
        )

    ndvi_max = float(df["NDVI"].max())
    if not shared.ndvi_looks_corrected(ndvi_max):
        print(
            f"WARNING: NDVI max is only {ndvi_max:.3f}. This looks like the "
            "pre-fix raw-DN export, so Heat_Risk is biased high and these tiers "
            "are indicative ranks at best."
        )

    # --- priority -----------------------------------------------------------
    df["priority"], low_cut, high_cut = assign_priority(df["Heat_Risk"])
    print(
        f"Heat_Risk cutoffs: Low <= {low_cut:.6f} < Medium < "
        f"{high_cut:.6f} <= High"
    )

    # --- vegetation class (descriptive; see Rule 2) -------------------------
    df["vegetation_class"] = np.where(
        df["NDVI"] < VEGETATION_NDVI_THRESHOLD, "sparse", "vegetated"
    )
    print(
        f"NDVI vegetation threshold (absolute): {VEGETATION_NDVI_THRESHOLD} "
        f"-> {(df['vegetation_class'] == 'vegetated').sum():,} vegetated / "
        f"{(df['vegetation_class'] == 'sparse').sum():,} sparse"
    )

    # --- action (land-cover aware; see Rule 3) ------------------------------
    assigned = [
        assign_action(lc, p)
        for lc, p in zip(df["land_cover"], df["priority"], strict=True)
    ]
    df["recommended_action"] = [a for a, _ in assigned]
    df["exclusion_reason"] = [r for _, r in assigned]

    excluded = df["recommended_action"] == "None"
    print(f"\nNo action: {excluded.sum():,} cells")
    print(df.loc[excluded, "exclusion_reason"].value_counts().to_string())

    # The safety property this whole rule exists for. Asserted rather than
    # trusted, because it is invisible in aggregate output and was wrong in
    # production for weeks.
    unsafe = df[
        df["land_cover"].isin(shared.NEVER_TOUCH)
        & (df["recommended_action"] != "None")
    ]
    if len(unsafe):
        raise AssertionError(
            f"{len(unsafe)} never-touch cells were assigned an intervention: "
            f"{unsafe['land_cover'].value_counts().to_dict()}"
        )

    # --- cost ---------------------------------------------------------------
    df["cell_area_m2"] = [cell_area_m2(g) for g in df["geo_json"]]
    # Looked up through the shared helper so an action name missing from the
    # catalogue raises KeyError instead of quietly becoming NaN - a silent NaN
    # here becomes a silently free intervention downstream.
    df["cost_estimate"] = [
        round(shared.action_cost(a, area))
        for a, area in zip(df["recommended_action"], df["cell_area_m2"], strict=True)
    ]
    df["cost_estimate"] = df["cost_estimate"].astype("int64")

    # --- expected cooling ---------------------------------------------------
    df["cooling_c"] = df["recommended_action"].map(shared.action_cooling_c)

    print(
        f"Cell area: mean {df['cell_area_m2'].mean():,.0f} m2 "
        f"(min {df['cell_area_m2'].min():,.0f}, max {df['cell_area_m2'].max():,.0f})"
    )

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(df):,} rows -> {OUTPUT_CSV.relative_to(MODULE_DIR)}")

    # --- summary ------------------------------------------------------------
    counts = df.groupby(["priority", "recommended_action"], as_index=False).agg(
        cells=("grid_id", "size"),
        total_cost_inr=("cost_estimate", "sum"),
        mean_lst=("LST", "mean"),
        mean_ndvi=("NDVI", "mean"),
    )
    print("\n" + counts.to_string(index=False))
    print(f"\nTotal notional programme cost: INR {df['cost_estimate'].sum():,}")

    # Mean cooling is merged in AFTER the console print above, deliberately:
    # widening `counts` itself would change the printed frame, and the printed
    # output of this script is treated as a stable contract. Only the markdown
    # report gains the column.
    summary = counts.merge(
        df.groupby(["priority", "recommended_action"], as_index=False).agg(
            mean_cooling_c=("cooling_c", "mean"),
        ),
        on=["priority", "recommended_action"],
        how="left",
    )

    lines = [
        "# Tiering and recommendation summary",
        "",
        "> Tiers are relative ranks within Guwahati (Heat_Risk quantiles), not "
        "calibrated absolute risk levels. Costs are planning placeholders.",
        ">",
        "> Expected cooling is a placeholder assumption, and not this module's "
        "own: the per-action degrees C originate in the Decision-Support "
        "catalogue, which labels them \"placeholder engineering estimates for "
        "a hackathon demo\". They are not measured, fitted or validated for "
        "Guwahati - see shared/constants.json.",
        ">",
        "> Interventions are gated on real ESA WorldCover land cover: water "
        "and wetland cells are never treated, built-up cells receive roof "
        "interventions only, and ground interventions are placed only on open "
        "land. See shared/uhi_shared.py:assign_action.",
        "",
        "## Thresholds actually applied",
        "",
        "| Rule | Value |",
        "|---|---|",
        f"| Heat_Risk q{LOW_QUANTILE:.2f} (Low boundary) | {low_cut:.6f} |",
        f"| Heat_Risk q{HIGH_QUANTILE:.2f} (High boundary) | {high_cut:.6f} |",
        f"| NDVI vegetation threshold (absolute) | {VEGETATION_NDVI_THRESHOLD} |",
        "",
        "## Land cover of the study area",
        "",
        "| Land cover | Cells |",
        "|---|---|",
        *[
            f"| {lc} | {n:,} |"
            for lc, n in df["land_cover"].value_counts().items()
        ],
        "",
        "## Why cells received no action",
        "",
        "| Reason | Cells |",
        "|---|---|",
        *[
            f"| {reason} | {n:,} |"
            for reason, n in df.loc[excluded, "exclusion_reason"]
            .value_counts()
            .items()
        ],
        "",
        "## Outcome",
        "",
        "| Priority | Action | Cells | Mean LST (C) | Mean NDVI | "
        "Total cost (INR) | Mean cooling (C, assumed) |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in summary.iterrows():
        lines.append(
            f"| {r['priority']} | {r['recommended_action']} | {r['cells']:,} | "
            f"{r['mean_lst']:.2f} | {r['mean_ndvi']:.3f} | {r['total_cost_inr']:,} | "
            f"{r['mean_cooling_c']:.2f} |"
        )
    lines += [
        "",
        f"**Total notional programme cost: INR {df['cost_estimate'].sum():,}** "
        "(placeholder unit rates - see README section 5).",
    ]
    (RESULTS_DIR / "tiering_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    # --- map ----------------------------------------------------------------
    colours = {"High": "#d7191c", "Medium": "#fdae61", "Low": "#2c7bb6"}
    fig, ax = plt.subplots(figsize=(9, 6))
    for tier in ["Low", "Medium", "High"]:
        sub = df[df["priority"] == tier]
        ax.scatter(
            sub["Longitude"],
            sub["Latitude"],
            s=4,
            c=colours[tier],
            label=f"{tier} ({len(sub):,})",
            edgecolors="none",
        )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Guwahati mitigation priority tiers (uncorrected NDVI - indicative)")
    ax.legend(title="Priority", loc="upper right", markerscale=3)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "priority_map.png", dpi=130)
    plt.close(fig)
    print("Wrote Results/tiering_summary.md, Results/priority_map.png")


if __name__ == "__main__":
    main()
