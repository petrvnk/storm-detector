"""Render-level regression tests for notification blueprint messages."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

homeassistant_template = pytest.importorskip("homeassistant.helpers.template")
Template = homeassistant_template.Template

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints" / "automation" / "storm_detector" / "storm_notification.yaml"
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


def _render_variable(hass: object, name: str, variables: dict[str, object]) -> str:
    rendered = Template(_blueprint_variable_template(name), hass).async_render(
        variables,
        parse_result=False,
    )
    return " ".join(rendered.split())


@pytest.mark.parametrize(
    ("language", "current_level", "evidence_kind", "expected"),
    [
        ("en", "warning", "lightning_only", "Thunderstorm / lightning nearby. Follow official weather warnings."),
        ("en", "warning", "radar_hail", "Radar indicates possible hail nearby. Radar activity is not confirmed hail; follow official warnings."),
        ("en", "urgent", "radar_hail_with_lightning", "Radar indicates high possible hail risk nearby. Lightning is also nearby. Radar activity is not confirmed hail; follow official warnings."),
        ("cs", "warning", "lightning_only", "Blízká bouřka / blesky poblíž. Sledujte oficiální výstrahy."),
        ("cs", "warning", "radar_hail", "Radar ukazuje možné kroupy poblíž. Radarová aktivita není potvrzené krupobití; sledujte oficiální výstrahy."),
        (
            "cs",
            "urgent",
            "radar_hail_with_lightning",
            "Radar ukazuje vysokou možnost krup poblíž. Blesky jsou také poblíž. Radarová aktivita není potvrzené krupobití; sledujte oficiální výstrahy.",
        ),
        ("en", "warning", "radar_storm", "Storm activity detected nearby. Follow official weather warnings."),
        ("cs", "warning", "radar_storm", "V okolí byla detekována bouřková aktivita. Sledujte oficiální výstrahy."),
        ("en", "warning", "unknown", "Current storm detection data is unavailable. Follow official weather warnings."),
        ("en", "warning", None, "Current storm detection data is unavailable. Follow official weather warnings."),
        ("cs", "warning", "unknown", "Aktuální data pro detekci bouřek nejsou dostupná. Sledujte oficiální výstrahy."),
        ("cs", "warning", None, "Aktuální data pro detekci bouřek nejsou dostupná. Sledujte oficiální výstrahy."),
    ],
)
def test_blueprint_message_renders_by_language_and_evidence(
    hass: object,
    language: str,
    current_level: str,
    evidence_kind: str | None,
    expected: str,
) -> None:
    normalized = _render_variable(
        hass,
        "message_text",
        {
            "title_language": language,
            "current_level": current_level,
            "evidence_kind": evidence_kind,
            "effective_evidence": evidence_kind,
            "degraded_sources": False,
            "summary_text": ENGLISH_SUMMARY,
            "detail_text": "",
        },
    )

    assert normalized == expected
    if language == "cs":
        assert ENGLISH_SUMMARY not in normalized
    if evidence_kind in {None, "unknown"}:
        assert "hail" not in normalized.lower()
        assert "kroup" not in normalized.lower()


@pytest.mark.parametrize(
    ("language", "current_level", "evidence_kind", "expected"),
    [
        ("en", "warning", "lightning_only", "Thunderstorm / lightning nearby"),
        ("cs", "warning", "lightning_only", "Blízká bouřka / blesky poblíž"),
        ("en", "urgent", "radar_hail", "High possible hail risk nearby"),
        ("cs", "urgent", "radar_hail_with_lightning", "Vysoká možnost krup"),
        ("en", "warning", "unknown", "Detection unavailable"),
        ("cs", "warning", None, "Detekce není dostupná"),
    ],
)
def test_blueprint_title_renders_exact_frozen_copy(
    hass: object,
    language: str,
    current_level: str,
    evidence_kind: str | None,
    expected: str,
) -> None:
    assert _render_variable(
        hass,
        "title_text",
        {
            "title_language": language,
            "current_level": current_level,
            "evidence_kind": evidence_kind,
            "effective_evidence": evidence_kind,
            "degraded_sources": False,
        },
    ) == expected


@pytest.mark.parametrize(
    (
        "language",
        "current_level",
        "source_status",
        "expected_evidence",
        "expected_title",
        "expected_message",
    ),
    [
        (
            "en",
            "warning",
            {"radar": "stale", "lightning": "ok"},
            "lightning_only",
            "Thunderstorm / lightning nearby",
            "Thunderstorm / lightning nearby. Follow official weather warnings. Some data sources are unavailable; use only current trusted evidence.",
        ),
        (
            "cs",
            "urgent",
            {"radar": "ok", "lightning": "stale"},
            "radar_hail",
            "Vysoká možnost krup",
            "Radar ukazuje vysokou možnost krup poblíž. Radarová aktivita není potvrzené krupobití; sledujte oficiální výstrahy. Některé zdroje dat nejsou dostupné; používejte jen aktuální důvěryhodné údaje.",
        ),
    ],
)
def test_blueprint_reduces_aggregate_stale_partial_sources_to_current_evidence(
    hass: object,
    language: str,
    current_level: str,
    source_status: dict[str, str],
    expected_evidence: str,
    expected_title: str,
    expected_message: str,
) -> None:
    base_variables: dict[str, object] = {
        "title_language": language,
        "current_level": current_level,
        "evidence_kind": "radar_hail_with_lightning",
        "source_status": source_status,
        "aggregate_stale": True,
    }
    effective_evidence = _render_variable(
        hass, "effective_evidence", base_variables
    )
    degraded_sources = (
        _render_variable(hass, "degraded_sources", base_variables).lower() == "true"
    )
    rendered_variables = {
        **base_variables,
        "effective_evidence": effective_evidence,
        "degraded_sources": degraded_sources,
    }

    assert effective_evidence == expected_evidence
    assert degraded_sources is True
    assert _render_variable(hass, "title_text", rendered_variables) == expected_title
    assert (
        _render_variable(hass, "message_text", rendered_variables)
        == expected_message
    )
