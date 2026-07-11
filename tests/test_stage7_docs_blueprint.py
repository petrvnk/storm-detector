"""Stage 7 documentation and notification blueprint tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
BLUEPRINT = ROOT / "blueprints" / "automation" / "radar_hail_risk" / "hail_risk_notification.yaml"


def test_readme_contains_manual_dashboard_snippets_and_no_auto_write_claims() -> None:
    text = README.read_text(encoding="utf-8")

    assert "Lovelace dashboard snippets" in text
    assert "manual examples only" in text
    assert "never writes dashboards automatically" in text
    assert "sensor.radar_hail_risk_level" in text
    assert "sensor.radar_hail_risk_summary" in text
    assert "binary_sensor.radar_hail_risk_active" in text
    assert "binary_sensor.radar_hail_risk_data_stale" in text
    assert "These four entities are enabled by default" in text
    assert "Notification blueprint" in text
    assert "Sledování bouřky" in text
    assert "Blízká bouřka / blesky poblíž" in text
    assert "Možné kroupy poblíž" in text
    assert "Vysoké riziko krup" in text
    assert "Open-Meteo is intentionally **not** part" in text


def test_notification_blueprint_is_opt_in_and_has_required_inputs() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    assert "domain: automation" in text
    assert "risk_level_sensor:" in text
    assert "risk_summary_sensor:" in text
    assert "notify_service:" in text
    assert "minimum_level:" in text
    assert "title_language:" in text
    assert "cooldown_minutes:" in text
    assert "max_dbz_sensor:" not in text
    assert "lightning_distance_sensor:" not in text
    assert "!input risk_level_sensor" in text
    assert "!input notify_service" in text
    assert "tag: radar_hail_risk" in text
    assert "Open-Meteo" not in text


def test_readme_blueprint_instructions_match_minimal_blueprint_inputs() -> None:
    readme = README.read_text(encoding="utf-8")
    blueprint = BLUEPRINT.read_text(encoding="utf-8")

    for input_name in (
        "risk_level_sensor",
        "risk_summary_sensor",
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

    assert "Vysoké riziko krup" in text
    assert "Možné kroupy poblíž" in text
    assert "Blízká bouřka / blesky poblíž" in text
    assert "Sledování bouřky" in text
    assert "High hail risk nearby" in text
    assert "Possible hail nearby" in text
    assert "Thunderstorm / lightning nearby" in text
    assert "Storm watch" in text


def test_blueprint_branches_titles_and_messages_on_evidence_kind() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    assert "state_attr(risk_level_entity, 'evidence_kind')" in text
    assert "evidence_kind == 'lightning_only'" in text
    assert "evidence_kind in ['radar_hail', 'radar_hail_with_lightning']" in text
    assert "hail not confirmed" in text
    assert "kroupy nejsou potvrzené" in text
    assert "Weather risk update" in text
    assert "Upozornění na počasí" in text
