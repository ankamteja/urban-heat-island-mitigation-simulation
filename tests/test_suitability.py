"""
Tests for the shared suitability rule.

These exist because the rule was correct in one module and absent in another for
weeks, and the difference was invisible in every aggregate summary the project
produced. Aggregates hid it; assertions do not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "shared"))

import uhi_shared as shared  # noqa: E402

TIERS = ["High", "Medium", "Low"]


# --------------------------------------------------------------------------
# The safety properties. These are the tests that would have caught the defect.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("land_cover", sorted(shared.NEVER_TOUCH))
@pytest.mark.parametrize("priority", TIERS)
def test_never_touch_land_cover_gets_no_intervention(land_cover, priority):
    """Water and wetland are never treated, however hot they are."""
    action, reason = shared.assign_action(land_cover, priority)
    assert action == "None"
    assert reason and land_cover in reason


@pytest.mark.parametrize("priority", TIERS)
def test_built_up_never_gets_a_ground_intervention(priority):
    """
    ESA WorldCover has no road class, so a built_up cell may be a road. A cool
    roof there is moot; a park there is not. Ground interventions must never be
    assigned to built-up land.
    """
    action, _ = shared.assign_action("built_up", priority)
    assert action in {"Cool roof", "None"}
    assert action not in {"Tree cover", "Green park"}


@pytest.mark.parametrize("land_cover", sorted(shared.GROUND_ELIGIBLE))
@pytest.mark.parametrize("priority", ["High", "Medium"])
def test_open_land_never_gets_a_roof_intervention(land_cover, priority):
    """You cannot install a cool roof on bare ground."""
    action, _ = shared.assign_action(land_cover, priority)
    assert action in {"Tree cover", "Green park"}


@pytest.mark.parametrize("land_cover", sorted(shared.ALREADY_GREEN))
@pytest.mark.parametrize("priority", TIERS)
def test_already_vegetated_land_gets_no_new_vegetation(land_cover, priority):
    action, reason = shared.assign_action(land_cover, priority)
    assert action == "None"
    assert "already vegetated" in reason


@pytest.mark.parametrize(
    "land_cover", sorted(shared.GROUND_ELIGIBLE | shared.ROOF_ELIGIBLE)
)
def test_low_priority_never_gets_an_intervention(land_cover):
    action, reason = shared.assign_action(land_cover, "Low")
    assert action == "None"
    assert "low priority" in reason


def test_unknown_land_cover_is_excluded_not_guessed():
    action, reason = shared.assign_action("unknown", "High")
    assert action == "None"
    assert "unclassified" in reason


# --------------------------------------------------------------------------
# Contract with the dashboard
# --------------------------------------------------------------------------

ALL_LAND_COVERS = sorted(set(shared.LANDCOVER_LABELS.values()) | {"unknown"})


@pytest.mark.parametrize("land_cover", ALL_LAND_COVERS)
@pytest.mark.parametrize("priority", TIERS)
def test_every_action_is_one_the_frontend_understands(land_cover, priority):
    """
    frontend/js/config.js keys INTERVENTIONS on these exact strings and
    export_grid_geojson.py enforces them. A label this rule can emit but the
    dashboard does not know renders as a blank popup, not an error.
    """
    action, _ = shared.assign_action(land_cover, priority)
    assert action in shared.VALID_ACTIONS


@pytest.mark.parametrize("land_cover", ALL_LAND_COVERS)
@pytest.mark.parametrize("priority", TIERS)
def test_exclusion_reason_is_present_exactly_when_no_action(land_cover, priority):
    action, reason = shared.assign_action(land_cover, priority)
    assert (action == "None") == (reason is not None)


# --------------------------------------------------------------------------
# Cost and cooling lookups
# --------------------------------------------------------------------------

def test_unknown_action_raises_rather_than_returning_nan():
    """
    A silent NaN cost becomes a silently free intervention downstream, and a
    silent NaN cooling becomes a cell that appears to need no treatment.
    """
    with pytest.raises(KeyError):
        shared.action_cost("Teleportation", 8918.0)
    with pytest.raises(KeyError):
        shared.action_cooling_c("Teleportation")


def test_no_action_costs_nothing_and_cools_nothing():
    assert shared.action_cost("None", 8918.0) == 0.0
    assert shared.action_cooling_c("None") == 0.0


@pytest.mark.parametrize(
    ("action", "expected_rate"),
    [("Tree cover", 37.5), ("Cool roof", 60.0), ("Green park", 115.0)],
)
def test_effective_rates_are_the_documented_values(action, expected_rate):
    """
    Pins the effective per-m2 rate, because it is a number that moves the
    conclusions and is easy to change without noticing what it does.

    Tree cover and cool roof still match the figures the Decision-Support module
    historically hardcoded (37.5 and 60.0). Green park deliberately no longer
    does: its rate was revised from 250 to 1,150 INR/m2 on 2026-08-14, anchored
    on real Gujarat AMRUT 2.0 municipal garden costs, because 250 was 5-9x below
    every comparable. That single number had made parks the most cost-effective
    intervention in the catalogue; correcting it removed parks from the funded
    set entirely. See shared/constants.json for provenance.
    """
    assert shared.effective_rate_inr_per_m2(action) == pytest.approx(expected_rate)


def test_cost_effectiveness_ordering_is_what_the_docs_claim():
    """
    The greedy budget ranking sorts on cooling per rupee, so this ordering is
    what decides which cells get funded. It is documented in
    docs/05-decision-support.md; assert it rather than leaving it to prose,
    since it already flipped once when a unit rate was corrected.
    """
    ratio = {
        action: shared.action_cooling_c(action)
        / shared.action_cost(action, 8918.0)
        for action in ("Tree cover", "Cool roof", "Green park")
    }
    assert ratio["Tree cover"] > ratio["Green park"] > ratio["Cool roof"], ratio


def test_cost_scales_linearly_with_area():
    assert shared.action_cost("Tree cover", 2000.0) == pytest.approx(
        2 * shared.action_cost("Tree cover", 1000.0)
    )


# --------------------------------------------------------------------------
# Land-cover mapping and NDVI provenance
# --------------------------------------------------------------------------

def test_land_cover_codes_map_to_labels():
    assert shared.land_cover_label(80) == "water"
    assert shared.land_cover_label(50) == "built_up"
    assert shared.land_cover_label(10) == "tree_cover"


def test_unmapped_or_missing_land_cover_is_unknown_not_a_crash():
    assert shared.land_cover_label(999) == "unknown"
    assert shared.land_cover_label(None) == "unknown"
    assert shared.land_cover_label(float("nan")) == "unknown"


def test_land_cover_categories_do_not_overlap():
    """
    A land cover in two categories makes assign_action's ordering silently
    load-bearing. Keep them disjoint.
    """
    groups = [
        shared.NEVER_TOUCH,
        shared.ALREADY_GREEN,
        shared.ROOF_ELIGIBLE,
        shared.GROUND_ELIGIBLE,
    ]
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            assert not (a & b), f"overlapping land-cover categories: {a & b}"


def test_ndvi_provenance_check_distinguishes_the_two_exports():
    """The pre-fix raw-DN export capped at ~0.386; the corrected one reaches ~0.78."""
    assert not shared.ndvi_looks_corrected(0.386)
    assert shared.ndvi_looks_corrected(0.781)
