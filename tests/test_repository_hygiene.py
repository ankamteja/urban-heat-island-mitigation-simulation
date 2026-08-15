"""Repository-level checks for licensing and the deployed dashboard artefacts."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent.parent
LICENSE = REPO_DIR / "LICENSE"
NOTICE = REPO_DIR / "NOTICE.md"
GRID = REPO_DIR / "frontend" / "data" / "grid.geojson"
RELEASE = REPO_DIR / "frontend" / "data" / "release.json"


def test_license_is_a_clean_mit_license_with_separate_data_notice():
    """Keep GitHub's license detector from being confused by attribution text."""
    license_text = LICENSE.read_text(encoding="utf-8")
    assert license_text.startswith("MIT License\n\nCopyright (c) ")
    assert "Permission is hereby granted, free of charge" in license_text
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in license_text
    assert "THIRD-PARTY DATA" not in license_text
    assert NOTICE.exists()
    assert "ESA WorldCover" in NOTICE.read_text(encoding="utf-8")


def test_release_manifest_identifies_the_exact_dashboard_grid():
    """A Vercel deployment must not pair current UI code with an old grid."""
    payload = GRID.read_bytes()
    manifest = json.loads(RELEASE.read_text(encoding="utf-8"))
    grid = json.loads(payload)
    properties = [feature["properties"] for feature in grid["features"]]
    counts: dict[str, int] = {}
    for row in properties:
        action = row["recommended_action"]
        counts[action] = counts.get(action, 0) + 1

    assert manifest["schema_version"] == 1
    assert manifest["grid_sha256"] == sha256(payload).hexdigest()
    assert manifest["release_id"] == manifest["grid_sha256"][:12]
    assert manifest["cell_count"] == len(properties)
    assert manifest["total_cost_inr"] == sum(row["cost_estimate"] for row in properties)
    assert manifest["action_counts"] == counts
