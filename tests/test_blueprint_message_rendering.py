"""Render-level regression tests for notification blueprint messages."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

homeassistant_template = pytest.importorskip("homeassistant.helpers.template")
Template = homeassistant_template.Template

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints" / "automation" / "radar_hail_risk" / "hail_risk_notification.yaml"
ENGLISH_SUMMARY = "English coordinator summary: hail warning"


def _blueprint_variable_template(name: str) -> str:
    lines = BLUEPRINT.read_text(encoding="utf-8").splitlines()
    marker = f"  {name}: >-"
    start = lines.index(marker) + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if lines[index].startswith("  ") and not lines[index].startswith("    ")
        ),
        len(lines),
    )
    return dedent("\n".join(lines[start:end]))


@pytest.mark.parametrize(
    ("language", "current_level", "evidence_kind", "expected"),
    [
        ("en", "warning", "lightning_only", "Thunderstorm / lightning nearby; hail not confirmed"),
        ("en", "warning", "radar_hail", ENGLISH_SUMMARY),
        ("en", "urgent", "radar_hail_with_lightning", ENGLISH_SUMMARY),
        ("cs", "warning", "lightning_only", "Blízká bouřka / blesky poblíž; kroupy nejsou potvrzené"),
        ("cs", "warning", "radar_hail", "Radar ukazuje možné kroupy poblíž"),
        (
            "cs",
            "urgent",
            "radar_hail_with_lightning",
            "Radar ukazuje vysoké riziko krup poblíž; blesky jsou také poblíž",
        ),
        ("en", "warning", "unknown", "Weather risk state changed; radar confirmation unavailable"),
        ("en", "warning", None, "Weather risk state changed; radar confirmation unavailable"),
        ("cs", "warning", "unknown", "Změna stavu počasí; radarové potvrzení není k dispozici"),
        ("cs", "warning", None, "Změna stavu počasí; radarové potvrzení není k dispozici"),
    ],
)
def test_blueprint_message_renders_by_language_and_evidence(
    hass: object,
    language: str,
    current_level: str,
    evidence_kind: str | None,
    expected: str,
) -> None:
    rendered = Template(_blueprint_variable_template("message_text"), hass).async_render(
        {
            "title_language": language,
            "current_level": current_level,
            "evidence_kind": evidence_kind,
            "summary_text": ENGLISH_SUMMARY,
            "detail_text": "",
        },
        parse_result=False,
    )
    normalized = " ".join(rendered.split())

    assert normalized == expected
    if language == "cs":
        assert ENGLISH_SUMMARY not in normalized
    if evidence_kind in {None, "unknown"}:
        assert "hail" not in normalized.lower()
        assert "kroup" not in normalized.lower()
