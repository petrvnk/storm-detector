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
        ROOT / "examples" / "lovelace" / "native-card.yaml",
        ROOT / "examples" / "lovelace" / "mushroom-card.yaml",
        ROOT / "examples" / "lovelace" / "weather-tab.yaml",
        ROOT / ".github" / "workflows" / "validate.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
    ]

    missing = [path for path in expected if not path.exists()]
    assert not missing, f"Missing release-readiness files: {missing}"


def test_manifest_and_hacs_metadata_are_release_ready() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "storm_detector" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == "storm_detector"
    assert manifest["version"] == "0.1.0"
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert hacs["name"] == "Storm Detector"
    assert hacs["homeassistant"] >= "2024.10.0"
    assert hacs["render_readme"] is True


def test_readme_contains_release_limitations_credits_and_migration_notes() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Install with HACS" in readme
    assert "https://github.com/petrvnk/storm-detector" in readme
    assert "Limitations" in readme
    assert "not an official warning source" in readme
    assert "Credits" in readme
    assert "RainViewer" in readme
    assert "Blitzortung-compatible" in readme
    assert "radar-only" in readme
    assert "examples/lovelace/native-card.yaml" in readme
    assert len(readme.splitlines()) < 180
    assert "unpushed RC" not in readme


def test_lovelace_examples_use_clean_entity_ids() -> None:
    examples_dir = ROOT / "examples" / "lovelace"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in examples_dir.glob("*.yaml"))

    assert "sensor.storm_detector_level" in combined
    assert "sensor.storm_detector_summary" in combined
    assert "binary_sensor.storm_detector_data_stale" in combined
    assert "device_tracker.storm_detector_storm_core" in combined


def test_notification_blueprint_includes_minimal_entities_and_cooldown() -> None:
    blueprint = (
        ROOT / "blueprints" / "automation" / "storm_detector" / "storm_notification.yaml"
    ).read_text(encoding="utf-8")

    assert "storm_level_sensor" in blueprint
    assert "storm_summary_sensor" not in blueprint
    assert "cooldown_minutes" in blueprint
    assert "message_text" in blueprint


def test_release_checklist_covers_runtime_and_migration_verification() -> None:
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "Home Assistant runtime verification" in checklist
    assert "Migration from another alerting setup" in checklist
    assert "Compare the previous risk level" in checklist
    assert "HACS validation" in checklist
    assert "not an official warning source" in checklist


def test_release_checklist_tag_matches_manifest_version() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "storm_detector" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert f"`v{manifest['version']}`" in checklist
    assert "`v0.0.1`" not in checklist


def test_bug_report_sets_safe_diagnostics_expectations() -> None:
    template = (
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
    ).read_text(encoding="utf-8")

    assert "omit" in template
    assert "identifying config" in template
    assert "location details" in template
    assert "review" in template
    assert "private entity names" in template
    assert "addresses" in template
    assert "log details" in template
