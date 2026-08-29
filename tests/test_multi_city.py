"""
Tests for the global lattice and the multi-city grid contract.

Two claims are load-bearing for the whole multi-city feature, and both were
believed to be false when the work started:

1. grid_id is not opaque. backend/refresh_dataset.py states the grid can never
   be regenerated because the ids come from an Earth Engine vectoriser. The ids
   are in fact indices into a global lattice anchored at (0, 0) with a cell size
   of 100 / 111319.4908 degrees, so any city snaps to the same lattice and a
   rebuild reproduces its ids exactly. An advisor recommended an id migration
   costing an estimated 40-60 broken tests on the assumption that the ids were
   opaque; it was rejected on the evidence this module now pins.

2. A city built by backend/build_city.py must be indistinguishable to the
   frontend from the committed Guwahati grid. The redesign in PR #14 widened
   the contract from 7 properties to 11 and the widening was silent: a city
   missing plan_rank loads, draws, and then funds zero cells at any budget,
   because the dashboard sorts the budget allocation on that integer alone.

Neither claim is visible in any aggregate the project prints, which is exactly
why they are assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
CITIES_DIR = REPO_DIR / "frontend" / "data" / "cities"
COMMITTED_GRID = REPO_DIR / "frontend" / "data" / "grid.geojson"
MANIFEST = REPO_DIR / "frontend" / "data" / "cities.json"

# The lattice constant, repeated here rather than imported.
#
# build_city.py importing its own constant and agreeing with itself proves
# nothing. The number that matters is the one Earth Engine used to cut the
# committed grid, and the only evidence for it is the committed grid. So the
# literal is written out and checked against ids nobody in this project chose.
METRES_PER_DEGREE = 111319.4908
CELL_SIZE_DEG = 100.0 / METRES_PER_DEGREE

# export_grid_geojson.py FRONTEND_PROPERTIES, post-redesign.
CONTRACT_PROPERTIES = frozenset({
    "grid_id", "temperature", "ndvi", "ndbi", "land_cover", "priority",
    "recommended_action", "exclusion_reason", "cost_estimate", "cooling_c",
    "plan_rank",
})


# build_city.py rounds polygon corners to 6 decimal places, so a corner can
# land a fraction below its exact lattice coordinate and floor() then reports
# the cell below. 1e-6 degrees is about 10 cm -- far tighter than any error
# that would matter and comfortably looser than the file's own rounding.
LATTICE_TOLERANCE_DEG = 1e-6


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_on_lattice(feature) -> None:
    """The polygon's south-west corner IS its grid_id, read as a lattice index."""
    gid = feature["properties"]["grid_id"]
    col, row = _parse_grid_id(gid)
    ring = feature["geometry"]["coordinates"][0]
    west = min(pt[0] for pt in ring)
    south = min(pt[1] for pt in ring)

    assert abs(west - col * CELL_SIZE_DEG) < LATTICE_TOLERANCE_DEG, (
        f"{gid}: west edge {west} is not lattice column {col} "
        f"({col * CELL_SIZE_DEG})")
    assert abs(south - row * CELL_SIZE_DEG) < LATTICE_TOLERANCE_DEG, (
        f"{gid}: south edge {south} is not lattice row {row} "
        f"({row * CELL_SIZE_DEG})")


def _parse_grid_id(grid_id: str) -> tuple[int, int]:
    """'+102027+29089' -> (102027, 29089). Both signs are always present."""
    body = grid_id[1:]
    for i, ch in enumerate(body):
        if ch in "+-":
            return int(grid_id[: i + 1]), int(body[i:])
    raise AssertionError(f"grid_id {grid_id!r} has no second sign")


def _cities() -> list[Path]:
    if not CITIES_DIR.exists():
        return []
    return sorted(p for p in CITIES_DIR.iterdir() if (p / "grid.geojson").exists())


def _city_params():
    """Built cities are data, not code, and a fresh clone may have none."""
    cities = _cities()
    if not cities:
        return [pytest.param(None, marks=pytest.mark.skip(reason="no cities built"))]
    return [pytest.param(c, id=c.name) for c in cities]


# --------------------------------------------------------------------------
# 1. The lattice
# --------------------------------------------------------------------------

def test_committed_grid_ids_decode_to_the_global_lattice():
    """The strongest available check that grid_id is a lattice index.

    Every id in the committed Earth Engine grid must equal floor(lon / S),
    floor(lat / S) for its own polygon's south-west corner. This is not a
    property of code in this repository -- the ids and the geometry were both
    produced by Earth Engine years before build_city.py existed. If it holds
    across 8,144 independent cells, the decode is not a coincidence.
    """
    if not COMMITTED_GRID.exists():
        pytest.skip("committed grid not present")

    grid = _load(COMMITTED_GRID)
    features = grid["features"]
    assert len(features) > 1000, "expected the full committed grid"

    for feature in features:
        _assert_on_lattice(feature)


def test_committed_cells_are_one_lattice_step_across():
    """The cell size is the lattice step, not merely close to it.

    A grid could decode to plausible integers and still be cut at, say, 90 m.
    Then a second city would tile at a different pitch and the two would not
    share a lattice, which is the whole basis for not migrating the ids.
    """
    if not COMMITTED_GRID.exists():
        pytest.skip("committed grid not present")

    for feature in _load(COMMITTED_GRID)["features"][:500]:
        ring = feature["geometry"]["coordinates"][0]
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        assert max(lons) - min(lons) == pytest.approx(CELL_SIZE_DEG, rel=1e-6)
        assert max(lats) - min(lats) == pytest.approx(CELL_SIZE_DEG, rel=1e-6)


def test_lattice_ids_are_unique_within_a_grid():
    """grid_id is the join key between grid.geojson, dataset.csv and
    ranking.csv. A duplicate silently merges two cells on any join."""
    if not COMMITTED_GRID.exists():
        pytest.skip("committed grid not present")
    ids = [f["properties"]["grid_id"] for f in _load(COMMITTED_GRID)["features"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("city_dir", _city_params())
def test_built_cities_share_the_committed_lattice(city_dir):
    """A built city snaps to the same lattice as the committed one.

    This is what makes ids comparable across cities and what makes a rebuild
    reproducible. Two cities that tile at different origins would produce two
    id spaces that happen to look alike.
    """
    for feature in _load(city_dir / "grid.geojson")["features"]:
        _assert_on_lattice(feature)


@pytest.mark.parametrize("city_dir", _city_params())
def test_built_city_ids_do_not_collide_with_the_committed_grid(city_dir):
    """Different places occupy different lattice cells.

    A global lattice only helps if it actually separates cities. An overlap
    would mean two different places claiming one id, and the join key would be
    ambiguous the moment two cities were loaded together.
    """
    if not COMMITTED_GRID.exists():
        pytest.skip("committed grid not present")
    committed = {f["properties"]["grid_id"] for f in _load(COMMITTED_GRID)["features"]}
    built = {f["properties"]["grid_id"] for f in _load(city_dir / "grid.geojson")["features"]}
    assert not (committed & built)


# --------------------------------------------------------------------------
# 2. The frontend contract
# --------------------------------------------------------------------------

@pytest.mark.parametrize("city_dir", _city_params())
def test_built_city_satisfies_the_eleven_property_contract(city_dir):
    """Exactly the 11 properties the dashboard reads -- no more, no fewer.

    Extra properties are as much a defect as missing ones: they are payload
    shipped to every visitor that nothing renders.
    """
    for i, feature in enumerate(_load(city_dir / "grid.geojson")["features"]):
        assert set(feature["properties"]) == CONTRACT_PROPERTIES, f"feature {i}"
        assert feature["geometry"]["type"] == "Polygon"


@pytest.mark.parametrize("city_dir", _city_params())
def test_plan_rank_is_a_dense_ranking_of_the_actionable_cells(city_dir):
    """plan_rank is the budget allocation order, and the browser sorts on it.

    It must be 1..N over exactly the actionable cells with 0 everywhere else. A
    gap or a duplicate does not raise anything: the dashboard funds a slightly
    different set than ranking.csv and both look entirely plausible.
    """
    props = [f["properties"] for f in _load(city_dir / "grid.geojson")["features"]]
    ranks = [p["plan_rank"] for p in props]

    assert all(isinstance(r, int) and not isinstance(r, bool) for r in ranks), \
        "plan_rank must be an int -- the browser sorts on it numerically"

    actionable = [p for p in props if p["recommended_action"] != "None"]
    assert sorted(p["plan_rank"] for p in actionable) == list(range(1, len(actionable) + 1))
    assert all(p["plan_rank"] == 0 for p in props if p["recommended_action"] == "None")


@pytest.mark.parametrize("city_dir", _city_params())
def test_ranking_csv_agrees_with_plan_rank(city_dir):
    """The downloadable ranking and the dashboard's order are the same order.

    They are produced by different code paths from the same frame. If they ever
    disagree, a user checking the CSV against the map finds two different plans
    and no way to tell which one the project stands behind.
    """
    import csv

    with (city_dir / "ranking.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    by_id = {
        f["properties"]["grid_id"]: f["properties"]["plan_rank"]
        for f in _load(city_dir / "grid.geojson")["features"]
    }
    assert rows, "ranking.csv is empty"
    for row in rows:
        assert int(row["rank"]) == by_id[row["grid_id"]]


# --------------------------------------------------------------------------
# 3. The safety property, in every city
# --------------------------------------------------------------------------

@pytest.mark.parametrize("city_dir", _city_params())
def test_never_touch_land_cover_is_never_given_an_intervention(city_dir):
    """Water and wetland are never treated, in any city.

    test_suitability.py proves the rule; this proves every shipped artefact
    obeys it. The rule was once correct in one module and absent in another for
    weeks, and no aggregate the project printed showed the difference -- the
    reason that file exists is the reason this assertion is repeated per city.
    """
    import sys
    sys.path.insert(0, str(REPO_DIR / "shared"))
    import uhi_shared as shared  # noqa: E402

    # NEVER_TOUCH holds the label strings, which is what land_cover carries.
    never = set(shared.NEVER_TOUCH)

    for feature in _load(city_dir / "grid.geojson")["features"]:
        p = feature["properties"]
        if p["land_cover"] in never:
            assert p["recommended_action"] == "None", \
                f"{p['grid_id']} is {p['land_cover']} and was given {p['recommended_action']}"
            assert p["cost_estimate"] == 0
            assert p["cooling_c"] == 0
            assert p["plan_rank"] == 0


@pytest.mark.parametrize("city_dir", _city_params())
def test_every_action_is_one_the_pipeline_recognises(city_dir):
    import sys
    sys.path.insert(0, str(REPO_DIR / "shared"))
    import uhi_shared as shared  # noqa: E402

    for feature in _load(city_dir / "grid.geojson")["features"]:
        assert feature["properties"]["recommended_action"] in shared.VALID_ACTIONS


# --------------------------------------------------------------------------
# 4. The manifest
# --------------------------------------------------------------------------

def test_manifest_matches_what_is_actually_on_disk():
    """cities.json is derived, never hand-edited.

    A manifest listing a city the repo does not have produces a dashboard entry
    that 404s on selection; a manifest missing a built city hides it entirely.
    """
    if not MANIFEST.exists():
        pytest.skip("no manifest")

    entries = _load(MANIFEST)["cities"]
    assert entries, "manifest lists no cities"

    listed = {e["slug"] for e in entries}
    on_disk = {p.name for p in _cities()}
    builtin = {e["slug"] for e in entries if e.get("builtin")}
    assert listed - builtin == on_disk

    for entry in entries:
        assert (REPO_DIR / "frontend" / entry["path"]).exists(), entry["slug"]
        assert isinstance(entry.get("cost_basis_applies"), bool), (
            f"{entry['slug']} must state whether the INR rate card applies")


@pytest.mark.parametrize("city_dir", _city_params())
def test_city_json_checksum_matches_its_own_grid(city_dir):
    """The integrity token the dashboard cache-busts on.

    A stale checksum serves a rebuilt city out of the browser cache, which is
    the failure that once presented as "the dashboard is not updating" against
    a server that had been serving the new file all along.
    """
    from hashlib import sha256

    meta = _load(city_dir / "city.json")
    payload = (city_dir / "grid.geojson").read_bytes()
    assert meta["grid_sha256"] == sha256(payload).hexdigest()
    assert meta["release_id"] == meta["grid_sha256"][:12]


@pytest.mark.parametrize("city_dir", _city_params())
def test_heat_risk_bounds_are_this_city_s_own(city_dir):
    """Heat_Risk is scaled per city, and the bounds must contain the data.

    unitScale(LST, 20, 34) was hardcoded from Guwahati. Nagpur's 2nd/98th
    percentiles are 40-48 degC, entirely above that ceiling: every cell would
    saturate at 1.0 and the priority tiers would become noise. The consequence
    is that tiers are not comparable between cities, which
    docs/08-limitations.md states.
    """
    meta = _load(city_dir / "city.json")
    lo, hi = meta["heat_risk_lst_scale"]
    assert lo < hi
    assert lo <= meta["mean_lst_c"] <= hi + 1e-9, "the mean falls outside the scale"
    assert meta["max_lst_c"] >= meta["mean_lst_c"]
