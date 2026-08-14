"""
Cross-module helpers shared by the Machine Learning and Decision-Support modules.

WHY THIS MODULE EXISTS
----------------------
Both Python modules independently implemented "which intervention should this
cell get". Only one of them (Decision-Support) applied a land-cover suitability
filter. The other (Machine Learning) did not - and the Machine Learning module
is the one that feeds the dashboard, so the deployed site recommended planting
trees on 148 water and wetland cells and placing parks on 3,433 built-up cells.

The rule was never wrong. It was just in the wrong module, and duplicated logic
is what let the two drift. Every constant and every suitability decision now
lives here, is imported by both modules, and is covered by tests/.

The modules live in directories containing spaces, which makes them awkward to
import from as packages. Callers therefore add this directory to sys.path and
import it by name:

    import sys
    sys.path.insert(0, str(REPO_DIR / "shared"))
    import uhi_shared as shared
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
CONSTANTS_PATH = Path(__file__).resolve().parent / "constants.json"

_DATASET_DIR = REPO_DIR / "Remote Sensing & Data Engineering" / "Dataset"


def load_constants() -> dict:
    """Parse shared/constants.json."""
    return json.loads(CONSTANTS_PATH.read_text(encoding="utf-8"))


CONSTANTS = load_constants()

ACTIONS: dict[str, dict] = CONSTANTS["actions"]
LAND_COVER = CONSTANTS["land_cover"]
TIERING = CONSTANTS["tiering"]

VALID_ACTIONS = frozenset(ACTIONS)

LANDCOVER_LABELS: dict[int, str] = {
    int(code): label for code, label in LAND_COVER["labels"].items()
}
NEVER_TOUCH = frozenset(LAND_COVER["never_touch"])
ALREADY_GREEN = frozenset(LAND_COVER["already_green"])
ROOF_ELIGIBLE = frozenset(LAND_COVER["roof_eligible"])
GROUND_ELIGIBLE = frozenset(LAND_COVER["ground_eligible"])


def source_dataset_path() -> Path:
    """
    Absolute path to the Remote Sensing module's exported grid dataset.

    Resolved through this one function so a rename cannot silently break two
    modules again - which is exactly what happened when the file was renamed
    from Guwahati_Urban_Heat_Dataset.csv to dataset.csv and neither consumer
    was updated. Both pipelines crashed on a clean clone until this landed.
    """
    path = _DATASET_DIR / CONSTANTS["dataset_filename"]
    if path.exists():
        return path

    # The file was renamed once already. If it is renamed again, fail with the
    # actual directory listing rather than a bare FileNotFoundError.
    candidates = sorted(p.name for p in _DATASET_DIR.glob("*.csv"))
    raise FileNotFoundError(
        f"Source dataset not found: {path}\n"
        f"CSV files present in {_DATASET_DIR}: {candidates or '(none)'}\n"
        "Update dataset_filename in shared/constants.json if it was renamed."
    )


def land_cover_label(code) -> str:
    """Map an ESA WorldCover numeric class to its label, or 'unknown'."""
    try:
        return LANDCOVER_LABELS.get(int(code), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def assign_action(land_cover: str, priority: str) -> tuple[str, str | None]:
    """
    The suitability rule. Returns (action, exclusion_reason).

    `action` is always one of VALID_ACTIONS; `exclusion_reason` is None when an
    intervention was assigned, and a human-readable string when the action is
    "None" so the decision is auditable rather than silently blank.

    Order matters and is deliberate:

      1. Never-touch land cover (water, wetland) wins over everything. A hot
         water cell is still water.
      2. Already-vegetated cells need no new vegetation.
      3. Low priority needs no intervention regardless of land cover.
      4. Built-up land gets roof interventions ONLY. WorldCover has no road
         class, so a built_up cell may be a road; a cool roof is moot there
         rather than harmful, whereas planting a park on it is not.
      5. Open land gets ground interventions only, sized by priority.
      6. Anything unclassified is excluded rather than guessed at.
    """
    if land_cover in NEVER_TOUCH:
        return "None", f"never-touch land cover ({land_cover})"
    if land_cover in ALREADY_GREEN:
        return "None", "already vegetated (tree cover) - no action needed"
    if priority == "Low":
        return "None", "low priority - no action needed"
    if land_cover in ROOF_ELIGIBLE:
        return "Cool roof", None
    if land_cover in GROUND_ELIGIBLE:
        # High-priority open land gets the larger intervention (a park);
        # medium-priority open land gets the lighter one (tree cover).
        return ("Green park" if priority == "High" else "Tree cover"), None
    return "None", f"unclassified land cover ({land_cover})"


def effective_rate_inr_per_m2(action: str) -> float:
    """
    Cost per treated square metre, already multiplied by coverage fraction.

    Raises KeyError on an unknown action rather than returning NaN - a silent
    NaN here becomes a silently-free intervention downstream.
    """
    spec = ACTIONS[action]
    return spec["inr_per_m2"] * spec["coverage_fraction"]


def action_cost(action: str, cell_area_m2: float) -> float:
    """Planning cost for one cell. See constants.json - placeholder rates."""
    return effective_rate_inr_per_m2(action) * cell_area_m2


def action_cooling_c(action: str) -> float:
    """Assumed temperature drop in degrees C. NOT a measurement."""
    return ACTIONS[action]["cooling_c"]


def ndvi_looks_corrected(ndvi_max: float) -> bool:
    """
    Whether an NDVI column looks like it came from the corrected export.

    The pre-fix Earth Engine script computed NDVI on raw DN values without the
    Landsat C2 L2 rescale, which compressed the whole city below ~0.39. The
    corrected export reaches ~0.78. Scripts warn based on this check rather
    than on a hardcoded caveat, because a hardcoded caveat about data is wrong
    the moment the data changes - which is precisely what happened: every
    script in this repo kept printing "NDVI is UNCORRECTED" for weeks after the
    corrected dataset had been committed.
    """
    return ndvi_max > 0.5
