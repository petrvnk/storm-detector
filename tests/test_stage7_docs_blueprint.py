"""Stage 7 documentation and notification blueprint tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
BLUEPRINT = ROOT / "blueprints" / "automation" / "storm_detector" / "storm_notification.yaml"


def test_readme_contains_manual_dashboard_snippets_and_no_auto_write_claims() -> None:
    text = README.read_text(encoding="utf-8")

    assert "Lovelace dashboard snippets" in text
    assert "manual examples only" in text
    assert "never writes dashboards automatically" in text
    assert "sensor.storm_detector_level" in text
    assert "sensor.storm_detector_summary" in text
    assert "binary_sensor.storm_detector_active" in text
    assert "binary_sensor.storm_detector_data_stale" in text
    assert "These four entities are enabled by default" in text
    assert "Notification blueprint" in text
    assert "Sledování bouřky" in text
    assert "Blízká bouřka / blesky poblíž" in text
    assert "Možné kroupy poblíž" in text
    assert "Vysoká možnost krup" in text
    assert "Open-Meteo is intentionally **not** part" in text


def test_notification_blueprint_is_opt_in_and_has_required_inputs() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    assert "domain: automation" in text
    assert "storm_level_sensor:" in text
    assert "storm_summary_sensor:" in text
    assert "level_entity:" not in text
    assert "summary_entity:" not in text
    assert "notify_service:" in text
    assert "minimum_level:" in text
    assert "title_language:" in text
    assert "cooldown_minutes:" in text
    assert "max_dbz_sensor:" not in text
    assert "lightning_distance_sensor:" not in text
    assert "default: sensor.storm_detector_level" in text
    assert "default: sensor.storm_detector_summary" in text
    assert "!input storm_level_sensor" in text
    assert "!input storm_summary_sensor" in text
    assert "!input notify_service" in text
    assert "tag: storm_detector" in text
    assert "https://github.com/petrvnk/storm-detector/blob/main/blueprints/automation/storm_detector/storm_notification.yaml" in text
    assert "Open-Meteo" not in text


def test_readme_blueprint_instructions_match_minimal_blueprint_inputs() -> None:
    readme = README.read_text(encoding="utf-8")
    blueprint = BLUEPRINT.read_text(encoding="utf-8")

    for input_name in (
        "storm_level_sensor",
        "storm_summary_sensor",
        "notify_service",
        "minimum_level",
        "title_language",
        "cooldown_minutes",
    ):
        assert f"{input_name}:" in blueprint
    assert "optional max dBZ sensor" not in readme
    assert "optional lightning distance sensor" not in readme


def test_blueprint_contains_czech_and_english_titles() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    assert "Vysoká možnost krup" in text
    assert "Možné kroupy poblíž" in text
    assert "Blízká bouřka / blesky poblíž" in text
    assert "Sledování bouřky" in text
    assert "High possible hail risk nearby" in text
    assert "Possible hail nearby" in text
    assert "Thunderstorm / lightning nearby" in text
    assert "Storm watch" in text


def test_blueprint_branches_titles_and_messages_on_evidence_kind() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    assert "state_attr(storm_level_sensor_id, 'evidence_kind')" in text
    assert "effective_evidence == 'lightning_only'" in text
    assert "effective_evidence in ['radar_hail', 'radar_hail_with_lightning']" in text
    assert "Storm / lightning nearby" not in text
    assert "hail is not radar-confirmed" not in text
    assert "kroupy nejsou radarově potvrzené" not in text
    assert "Follow official weather warnings" in text
    assert "Sledujte oficiální výstrahy" in text
    assert "Detection unavailable" in text
    assert "Detekce není dostupná" in text
    assert "Detection degraded" in text
    assert "Detekce je omezená" in text
