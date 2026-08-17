"""Home Assistant translation-resolution coverage for Storm Detector."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from custom_components.storm_detector.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "custom_components" / DOMAIN / "translations"


def test_english_and_czech_translation_contracts_are_complete() -> None:
    english = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    czech = json.loads((TRANSLATIONS / "cs.json").read_text(encoding="utf-8"))

    assert english.keys() == czech.keys()
    assert _leaf_paths(english) == _leaf_paths(czech)
    assert "services" not in english
    assert "services" not in czech


@pytest.mark.skipif(
    importlib.util.find_spec("homeassistant") is None,
    reason="Home Assistant test stack is not installed",
)
@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "Setup Storm Detector"), ("cs", "Nastavení Storm Detector")],
)
async def test_home_assistant_resolves_config_flow_translations(
    hass, language: str, expected: str
) -> None:
    translations = await _ha_translations(hass, language, "config")
    assert translations[f"component.{DOMAIN}.config.step.user.title"] == expected
    assert f"component.{DOMAIN}.config.step.user.data.location_entity_id" in translations


@pytest.mark.skipif(
    importlib.util.find_spec("homeassistant") is None,
    reason="Home Assistant test stack is not installed",
)
@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "Storm Detector options"), ("cs", "Možnosti Storm Detector")],
)
async def test_home_assistant_resolves_options_flow_translations(
    hass, language: str, expected: str
) -> None:
    translations = await _ha_translations(hass, language, "options")
    assert translations[f"component.{DOMAIN}.options.step.init.title"] == expected
    assert f"component.{DOMAIN}.options.step.init.data.core_watch_dbz" in translations


@pytest.mark.skipif(
    importlib.util.find_spec("homeassistant") is None,
    reason="Home Assistant test stack is not installed",
)
@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "Level"), ("cs", "Úroveň")],
)
async def test_home_assistant_resolves_entity_translations(
    hass, language: str, expected: str
) -> None:
    translations = await _ha_translations(hass, language, "entity")
    assert translations[f"component.{DOMAIN}.entity.sensor.level.name"] == expected
    assert f"component.{DOMAIN}.entity.device_tracker.storm_core.name" in translations


async def _ha_translations(hass, language: str, category: str) -> dict[str, str]:
    from homeassistant.helpers.translation import async_get_translations

    return await async_get_translations(
        hass,
        language,
        category,
        integrations={DOMAIN},
    )


def _leaf_paths(value: object, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if not isinstance(value, dict):
        return {prefix}
    return {
        path
        for key, child in value.items()
        for path in _leaf_paths(child, (*prefix, key))
    }
