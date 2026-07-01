"""Stage 8 HACS release-readiness tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_readiness_files_exist() -> None:
    expected = [
        ROOT / "LICENSE",
        ROOT / "CHANGELOG.md",
        ROOT / "docs" / "release-checklist.md",
        ROOT / ".github" / "workflows" / "validate.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
    ]

    missing = [path for path in expected if not path.exists()]
    assert not missing, f"Missing release-readiness files: {missing}"


def test_manifest_and_hacs_metadata_are_release_ready() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "radar_hail_risk" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == "radar_hail_risk"
    assert manifest["version"] == "0.0.1"
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")
    assert manifest["config_flow"] is True
    assert hacs["name"] == "Radar Hail Risk"
    assert hacs["homeassistant"] >= "2024.10.0"
    assert hacs["render_readme"] is True


def test_readme_contains_release_limitations_credits_and_migration_notes() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Install via HACS custom repository" in readme
    assert "Limitations and safety notes" in readme
    assert "not an official warning source" in readme
    assert "Credits" in readme
    assert "RainViewer" in readme
    assert "Blitzortung-compatible" in readme
    assert "If migrating from an older local watcher" in readme
    assert "radar-only mode" in readme
    assert "hacs/action@main" in readme


def test_release_checklist_covers_runtime_and_migration_verification() -> None:
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "Home Assistant runtime verification" in checklist
    assert "Migration from local watcher" in checklist
    assert "Compare local watcher risk level" in checklist
    assert "HACS validation" in checklist
    assert "not an official warning source" in checklist
