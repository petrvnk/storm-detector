"""Real Home Assistant execution tests for the notification blueprint."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")
automation_config = pytest.importorskip("homeassistant.components.automation.config")
blueprint_models = pytest.importorskip("homeassistant.components.blueprint.models")
ha_const = pytest.importorskip("homeassistant.const")
ha_setup = pytest.importorskip("homeassistant.setup")
yaml_util = pytest.importorskip("homeassistant.util.yaml")

AUTOMATION_BLUEPRINT_SCHEMA = automation_config.AUTOMATION_BLUEPRINT_SCHEMA
Blueprint = blueprint_models.Blueprint
BlueprintInputs = blueprint_models.BlueprintInputs
ATTR_FRIENDLY_NAME = ha_const.ATTR_FRIENDLY_NAME
async_setup_component = ha_setup.async_setup_component

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints" / "automation" / "storm_detector" / "storm_notification.yaml"
LEVEL_ENTITY = "sensor.release_safety_storm_level"
NOTIFY_SERVICE = "capture_release_safety_notification"
AUTOMATION_ENTITY = "automation.release_safety_blueprint_behavior"


def _generated_automation() -> dict[str, Any]:
    """Load and generate the automation through Home Assistant's blueprint model."""
    blueprint = Blueprint(
        yaml_util.load_yaml(BLUEPRINT),
        path=str(BLUEPRINT),
        expected_domain="automation",
        schema=AUTOMATION_BLUEPRINT_SCHEMA,
    )
    return BlueprintInputs(
        blueprint,
        {
            "id": "release_safety_blueprint_behavior",
            "alias": "Release safety blueprint behavior",
            "use_blueprint": {
                "path": "storm_detector/storm_notification.yaml",
                "input": {
                    "storm_level_sensor": LEVEL_ENTITY,
                    "notify_service": f"notify.{NOTIFY_SERVICE}",
                    "minimum_level": "warning",
                    "title_language": "en",
                    "cooldown_minutes": 30,
                },
            },
        },
    ).async_substitute()


async def _set_level(hass: Any, state: str, **attributes: Any) -> None:
    hass.states.async_set(
        LEVEL_ENTITY,
        state,
        {ATTR_FRIENDLY_NAME: "Release safety storm level", **attributes},
    )
    await hass.async_block_till_done()


async def _setup_automation(hass: Any) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []

    async def capture_notification(call: Any) -> None:
        notifications.append(dict(call.data))

    hass.services.async_register("notify", NOTIFY_SERVICE, capture_notification)
    await _set_level(
        hass,
        "none",
        evidence_kind="none",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert await async_setup_component(hass, "automation", {"automation": [_generated_automation()]})
    await hass.async_block_till_done()
    return notifications


def _last_triggered(hass: Any) -> Any:
    return hass.states.get(AUTOMATION_ENTITY).attributes.get("last_triggered")


@pytest.mark.asyncio
async def test_attribute_only_update_does_not_trigger_or_consume_cooldown(hass: Any) -> None:
    notifications = await _setup_automation(hass)

    await _set_level(
        hass,
        "none",
        evidence_kind="none",
        source_status={"radar": "ok", "lightning": "ok"},
        update_marker=1,
    )
    assert notifications == []
    assert _last_triggered(hass) is None
    await _set_level(
        hass,
        "warning",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_below_minimum_transition_does_not_consume_cooldown(hass: Any) -> None:
    notifications = await _setup_automation(hass)

    await _set_level(
        hass,
        "watch",
        evidence_kind="radar_storm",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert notifications == []
    assert _last_triggered(hass) is None
    await _set_level(
        hass,
        "warning",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_first_qualifying_transition_notifies(hass: Any) -> None:
    notifications = await _setup_automation(hass)

    await _set_level(
        hass,
        "warning",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert len(notifications) == 1
    assert _last_triggered(hass) is not None


@pytest.mark.asyncio
async def test_qualifying_transition_within_cooldown_does_not_notify(
    hass: Any, freezer: Any
) -> None:
    notifications = await _setup_automation(hass)

    await _set_level(
        hass,
        "warning",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    first_triggered = _last_triggered(hass)

    freezer.tick(timedelta(minutes=29))
    await _set_level(
        hass,
        "urgent",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert len(notifications) == 1
    assert _last_triggered(hass) == first_triggered


@pytest.mark.asyncio
async def test_qualifying_transition_after_elapsed_cooldown_notifies(
    hass: Any, freezer: Any
) -> None:
    notifications = await _setup_automation(hass)

    await _set_level(
        hass,
        "warning",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    first_triggered = _last_triggered(hass)

    freezer.tick(timedelta(minutes=30, seconds=1))
    await _set_level(
        hass,
        "urgent",
        evidence_kind="radar_hail",
        source_status={"radar": "ok", "lightning": "ok"},
    )
    assert len(notifications) == 2
    assert _last_triggered(hass) > first_triggered
