"""
Integration tests over the committed data products.

The defect these exist to prevent is not a crash - it is silence. The dashboard
served a grid built from a superseded dataset for weeks while every script,
every summary and every audit document reported success. Nothing was broken in
a way anything checked.

These tests check the committed artefacts against each other and against the
source data, so drift fails CI instead of shipping.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "shared"))

import uhi_shared as shared  # noqa: E402

ML_RESULTS = REPO_DIR / "Machine Learning & Prediction" / "Results"
FRONTEND_GEOJSON = REPO_DIR / "frontend" / "data" / "grid.geojson"
DS_DIR = REPO_DIR / "Decision-Support"

STRING_COLUMNS = ["grid_id", "priority", "recommended_action"]


@pytest.fixture(scope="module")
def dataset() -> pd.DataFrame:
    return pd.read_csv(shared.source_dataset_path())


@pytest.fixture(scope="module")
def tiered() -> pd.DataFrame:
    path = ML_RESULTS / "tiered.csv"
    if not path.exists():
        pytest.skip("tiered.csv not built - run the ML pipeline")
    # "None" is a real action label, not a missing value.
    return pd.read_csv(
        path, keep_default_na=False, na_values={c: [] for c in STRING_COLUMNS}
    )


@pytest.fixture(scope="module")
def frontend_cells() -> pd.DataFrame:
    if not FRONTEND_GEOJSON.exists():
        pytest.skip("frontend grid.geojson not built")
    payload = json.loads(FRONTEND_GEOJSON.read_text(encoding="utf-8"))
    return pd.DataFrame(
        [f["properties"] for f in payload["features"]]
    ).assign(grid_id=lambda d: d.grid_id.astype(str))


# --------------------------------------------------------------------------
# The source dataset must be the corrected export
# --------------------------------------------------------------------------

def test_source_dataset_resolves():
    """
    This is the test that would have caught the rename. The dataset was renamed
    from Guwahati_Urban_Heat_Dataset.csv to dataset.csv and both consuming
    modules kept the old name, so both crashed on a clean clone.
    """
    assert shared.source_dataset_path().exists()


def test_dataset_carries_the_corrected_export_columns(dataset):
    for column in ("LandCover", "NDBI", "Vegetation", "Latitude", "Longitude"):
        assert column in dataset.columns


def test_dataset_ndvi_is_the_corrected_range(dataset):
    assert shared.ndvi_looks_corrected(float(dataset["NDVI"].max()))


# --------------------------------------------------------------------------
# The live dashboard grid must be safe, current, and internally consistent
# --------------------------------------------------------------------------

def test_dashboard_never_recommends_work_on_water_or_wetland(
    frontend_cells, dataset
):
    """
    The headline defect. Before the land-cover fix, the deployed dashboard
    assigned tree planting or a park to 148 water and wetland cells.
    """
    merged = frontend_cells.merge(
        dataset.assign(grid_id=dataset.grid_id.astype(str))[["grid_id", "LandCover"]],
        on="grid_id",
    )
    merged["land_cover"] = merged["LandCover"].map(shared.land_cover_label)
    offenders = merged[
        merged["land_cover"].isin(shared.NEVER_TOUCH)
        & (merged["recommended_action"] != "None")
    ]
    assert offenders.empty, (
        f"{len(offenders)} never-touch cells carry an intervention: "
        f"{offenders.groupby(['land_cover', 'recommended_action']).size().to_dict()}"
    )


def test_dashboard_never_puts_ground_interventions_on_built_up_land(
    frontend_cells, dataset
):
    merged = frontend_cells.merge(
        dataset.assign(grid_id=dataset.grid_id.astype(str))[["grid_id", "LandCover"]],
        on="grid_id",
    )
    merged["land_cover"] = merged["LandCover"].map(shared.land_cover_label)
    offenders = merged[
        (merged["land_cover"] == "built_up")
        & merged["recommended_action"].isin(["Tree cover", "Green park"])
    ]
    assert offenders.empty, f"{len(offenders)} built-up cells got ground work"


def test_dashboard_grid_is_not_stale(frontend_cells, dataset):
    """
    Every cell in the dashboard must carry the temperature the current dataset
    reports. This is the staleness check: the committed grid was built from a
    superseded dataset and nothing detected it.
    """
    merged = frontend_cells.merge(
        dataset.assign(grid_id=dataset.grid_id.astype(str))[["grid_id", "LST"]],
        on="grid_id",
    )
    assert len(merged) == len(frontend_cells)
    drift = (merged["temperature"] - merged["LST"]).abs()
    # The export rounds temperature to 1 dp.
    assert drift.max() <= 0.05001, f"max temperature drift {drift.max():.3f} C"


def test_dashboard_actions_are_all_renderable(frontend_cells):
    unknown = set(frontend_cells["recommended_action"]) - set(shared.VALID_ACTIONS)
    assert not unknown, f"dashboard carries unrenderable actions: {unknown}"


def test_dashboard_cost_and_cooling_are_numeric(frontend_cells):
    """
    compareView.js computes temperature - cooling_c and popup.js calls
    .toLocaleString() on cost_estimate. A string in either field does not
    crash - it silently renders nonsense.
    """
    assert pd.api.types.is_numeric_dtype(frontend_cells["cooling_c"])
    assert pd.api.types.is_numeric_dtype(frontend_cells["cost_estimate"])


def test_no_action_cells_carry_no_cost_and_no_cooling(frontend_cells):
    idle = frontend_cells[frontend_cells["recommended_action"] == "None"]
    assert (idle["cooling_c"] == 0).all()
    assert (idle["cost_estimate"] == 0).all()


# --------------------------------------------------------------------------
# The two recommendation engines must agree
# --------------------------------------------------------------------------

def test_ml_and_decision_support_agree_on_every_cell(tiered):
    """
    Both modules now call the same suitability rule, so their action per cell
    must be identical. They previously disagreed completely: Decision-Support
    applied land cover and the ML module did not.
    """
    ds_path = DS_DIR / "recommendation.csv"
    if not ds_path.exists():
        pytest.skip("Decision-Support outputs not built")
    ds = pd.read_csv(ds_path).assign(grid_id=lambda d: d.grid_id.astype(str))
    ml = tiered.assign(grid_id=lambda d: d.grid_id.astype(str))

    merged = ds.merge(
        ml[["grid_id", "recommended_action"]],
        on="grid_id",
        suffixes=("_ds", "_ml"),
    )
    assert len(merged) == len(ds)
    mismatched = merged[
        merged["recommended_action_ds"] != merged["recommended_action_ml"]
    ]
    assert mismatched.empty, f"{len(mismatched)} cells disagree between modules"


def test_decision_support_ranking_is_deterministically_ordered():
    """
    Ties are the normal case in this ranking, not an edge case: cost uses a flat
    cell area, so every cell sharing an action has an identical
    cooling_per_rupee -- all 3,494 cool-roof cells score exactly the same.

    With pandas' default (unstable) quicksort the order within a tie was
    arbitrary, and ranking.csv failed to reproduce: 4,154 of 4,157 rows moved
    between identical runs. CI caught it. The fix is a stable sort plus explicit
    tie-breaks -- LST descending, then grid_id -- which this asserts.
    """
    path = DS_DIR / "ranking.csv"
    if not path.exists():
        pytest.skip("Decision-Support outputs not built")
    ranking = pd.read_csv(path)

    expected = ranking.sort_values(
        ["cooling_per_rupee", "LST", "grid_id"],
        ascending=[False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    assert list(ranking["grid_id"]) == list(expected["grid_id"]), (
        "ranking.csv is not in (cooling_per_rupee desc, LST desc, grid_id asc) "
        "order -- the sort lost its tie-break and the file will not reproduce"
    )
    assert list(ranking["rank"]) == list(range(1, len(ranking) + 1))


def test_grid_plan_rank_reproduces_the_decision_support_ranking():
    """
    The dashboard re-runs the budget client-side when a planner filters by area
    or priority, so it needs the funding order in the browser. It reads
    plan_rank from grid.geojson and sorts on nothing else.

    That only stays honest if plan_rank IS the pipeline's order. Deriving it in
    JavaScript from the exported fields does not work -- temperature ships at
    1 dp and cooling_per_rupee has three distinct values, so cells tie at a
    precision the pipeline never saw, and the browser funded a set with the same
    size, cost and mean cooling as ranking.csv and not one cell in common.

    This asserts the two orders agree cell for cell.
    """
    grid_path = REPO_DIR / "frontend" / "data" / "grid.geojson"
    ranking_path = DS_DIR / "ranking.csv"
    if not grid_path.exists() or not ranking_path.exists():
        pytest.skip("grid or Decision-Support outputs not built")

    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    plan_rank = {
        f["properties"]["grid_id"]: f["properties"]["plan_rank"]
        for f in grid["features"]
    }
    ranking = pd.read_csv(ranking_path)

    # Non-actionable cells are never funded at any budget.
    idle = [f for f in grid["features"]
            if f["properties"]["recommended_action"] == "None"]
    assert all(f["properties"]["plan_rank"] == 0 for f in idle)

    mismatched = [
        (row.grid_id, plan_rank.get(row.grid_id), row.rank)
        for row in ranking.itertuples()
        if plan_rank.get(row.grid_id) != row.rank
    ]
    assert not mismatched, (
        f"{len(mismatched)} cells rank differently in grid.geojson than in "
        f"ranking.csv, e.g. {mismatched[:3]} -- the dashboard would fund a "
        "different set than the committed plan"
    )


def test_funded_shortlist_is_heat_prioritised():
    """
    The budget cut-off should spend on the hottest eligible cells, not the ones
    that happen to sort first spatially.

    Before LST entered the sort, cooling_per_rupee's three distinct values (one
    per action, because cost is a flat cell area) left 3,494 cool-roof cells tied
    and grid_id decided the funded 249. Their mean temperature was 28.69 C while
    the 249 hottest cool-roof cells averaged 30.16 C -- the shortlist was
    reproducible but not heat-prioritised, which is the property the product
    actually claims.
    """
    path = DS_DIR / "ranking.csv"
    if not path.exists():
        pytest.skip("Decision-Support outputs not built")
    ranking = pd.read_csv(path)

    funded = ranking[ranking["within_budget"]]
    assert len(funded) > 0

    # Within each action group the funded cells must be the hottest available.
    for action, group in ranking.groupby("recommended_action"):
        picked = group[group["within_budget"]]
        if picked.empty or len(picked) == len(group):
            continue
        assert picked["LST"].min() >= group[~group["within_budget"]]["LST"].max(), (
            f"funded {action} cells are not the hottest ones available -- "
            "the budget is being spent by scan order, not by heat"
        )


def test_ml_readme_quotes_the_committed_metrics():
    """
    The module README documents the model scores in prose. Prose does not
    regenerate when the pipeline does, so it silently rots -- the README spent a
    while quoting an R2 of 0.1510 against a committed metrics.json saying 0.5130,
    which is the difference between "barely beats the mean" and "usable".

    Asserting the numbers appear verbatim is crude but catches exactly that.
    """
    metrics_path = ML_RESULTS / "metrics.json"
    readme_path = REPO_DIR / "Machine Learning & Prediction" / "README.md"
    if not (metrics_path.exists() and readme_path.exists()):
        pytest.skip("metrics.json not built")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    readme = readme_path.read_text(encoding="utf-8")

    missing = [
        f"{r['split']}/{r['features']}/{r['model']} R2={r['r2']:.4f}"
        for r in metrics["results"]
        if f"{r['r2']:.4f}" not in readme
    ]
    assert not missing, f"README does not quote these committed scores: {missing}"

    stale = [
        value for value in ("0.9010", "0.1510", "-0.0245", "0.179546")
        if value in readme
    ]
    assert not stale, f"README still quotes superseded figures: {stale}"


def test_tiered_costs_match_the_shared_rate_table(tiered):
    recomputed = [
        round(shared.action_cost(action, area))
        for action, area in zip(
            tiered["recommended_action"], tiered["cell_area_m2"], strict=True
        )
    ]
    assert list(tiered["cost_estimate"]) == recomputed
