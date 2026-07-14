"""Behavior tests for the adaptive Radar Hail Risk Lovelace card."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js"


def _render(states: dict[str, dict[str, object]]) -> str:
    source = CARD.read_text(encoding="utf-8").replace(
        "customElements.define('radar-hail-risk-card', RadarHailRiskCard);",
        "globalThis.TestCard = RadarHailRiskCard;\n"
        "customElements.define('radar-hail-risk-card', RadarHailRiskCard);",
    )
    script = f"""
globalThis.HTMLElement = class {{
  attachShadow() {{ this.shadowRoot = {{ innerHTML: '' }}; return this.shadowRoot; }}
}};
globalThis.customElements = {{ define() {{}} }};
globalThis.window = {{ customCards: [] }};
{source}
const card = new globalThis.TestCard();
card.setConfig({{}});
card.hass = {{ states: {json.dumps(states)} }};
process.stdout.write(card.shadowRoot.innerHTML);
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _states(
    level: str,
    *,
    evidence_kind: str,
    stale: bool = False,
    attributes: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    attrs: dict[str, object] = {
        "evidence_kind": evidence_kind,
        "is_stale": stale,
        "source_status": {"radar": "ok", "lightning": "not_configured"},
    }
    attrs.update(attributes or {})
    return {
        "sensor.radar_hail_risk_level": {"state": level, "attributes": attrs},
        "sensor.radar_hail_risk_summary": {"state": "Internal summary", "attributes": {}},
        "binary_sensor.radar_hail_risk_active": {
            "state": "off" if level in {"none", "unavailable"} else "on",
            "attributes": {},
        },
        "binary_sensor.radar_hail_risk_data_stale": {
            "state": "on" if stale else "off",
            "attributes": {},
        },
    }


def test_clear_state_is_compact_and_hides_diagnostics() -> None:
    html = _render(_states("none", evidence_kind="none"))

    assert "Silné radarové jádro v okolí nezjištěno" in html
    assert "Max dBZ" not in html
    assert "Confidence" not in html
    assert "<svg" not in html


def test_lightning_only_warning_never_claims_hail() -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="lightning_only",
            attributes={
                "lightning_distance_km": 14.2,
                "source_status": {"radar": "ok", "lightning": "ok"},
            },
        )
    )

    assert "Blesky poblíž" in html
    assert "Kroupy nejsou radarově potvrzené" in html
    assert "Možné kroupy" not in html
    assert "14.2 km" in html


def test_hail_wording_requires_radar_hail_evidence() -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "selected_core_distance_km": 12.4,
                "storm_approaching": True,
                "storm_eta_minutes": 23,
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert "Možné kroupy" in html
    assert "12.4 km" in html
    assert "Přibližuje se" in html
    assert "přibližně 20–25 min" in html


def test_high_hail_state_requires_urgent_radar_hail_evidence() -> None:
    html = _render(
        _states(
            "urgent",
            evidence_kind="radar_hail",
            attributes={
                "selected_core_distance_km": 6.1,
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert "Vysoká možnost krup" in html
    assert "6.1 km" in html


def test_stale_state_hides_previous_event_values() -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            stale=True,
            attributes={
                "selected_core_distance_km": 3.2,
                "storm_approaching": True,
                "storm_eta_minutes": 5,
            },
        )
    )

    assert "Detekce dočasně není dostupná" in html
    assert "Možné kroupy" not in html
    assert "3.2 km" not in html
    assert "ETA" not in html


def test_unreliable_or_stale_optional_values_are_omitted() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 31.0,
                "storm_approaching": None,
                "storm_eta_minutes": 18,
                "lightning_distance_km": 7.0,
                "source_status": {"radar": "ok", "lightning": "stale"},
            },
        )
    )

    assert "Bouřka v okolí" in html
    assert "31.0 km" in html
    assert "ETA" not in html
    assert "7.0 km" not in html
    assert "Confidence" not in html


def test_radar_storm_shows_core_intensity_and_area() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 63.4,
                "selected_core_max_dbz": 56,
                "selected_core_area_km2": 18.7,
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert 'aria-label="Poloha bouřkového jádra vůči domovu"' in html
    assert "63.4 km" in html
    assert "Intenzita jádra" in html
    assert "56 dBZ" in html
    assert "Plocha jádra" in html
    assert "18.7 km²" in html


def test_schematic_uses_core_bearing_not_motion_bearing() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 40.0,
                "storm_motion_bearing": 0.0,
                "storm_cores": [{"distance_km": 40.0, "bearing_degrees": 180.0}],
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    match = re.search(r'class="core-node" cx="([^"]+)" cy="([^"]+)"', html)
    assert match is not None
    x, y = (float(value) for value in match.groups())
    assert abs(x - 90) < 1
    assert y > 130
