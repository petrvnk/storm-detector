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
    assert "Notification blueprint" in text
    assert "Sledování bouřky" in text
    assert "Varování před kroupami" in text
    assert "Nebezpečí krup" in text
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
    assert "!input risk_level_sensor" in text
    assert "!input notify_service" in text
    assert "tag: radar_hail_risk" in text
    assert "Open-Meteo" not in text


def test_blueprint_contains_czech_and_english_titles() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    assert "Nebezpečí krup" in text
    assert "Varování před kroupami" in text
    assert "Sledování bouřky" in text
    assert "Hail risk urgent" in text
    assert "Hail risk warning" in text
    assert "Storm watch" in text
