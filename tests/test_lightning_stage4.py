"""Tests for Blitzortung-compatible lightning source helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from custom_components.radar_hail_risk.lightning import (
    HomeAssistantLightningSource,
    autodetect_blitzortung_entities,
    build_lightning_snapshot,
    normalize_counter_state,
    normalize_numeric_state,
)


@dataclass
class FakeState:
    entity_id: str
    state: str
    attributes: dict[str, Any]
    last_updated: datetime


class FakeStates:
    def __init__(self, states: dict[str, FakeState]) -> None:
        self._states = states

    def get(self, entity_id: str) -> FakeState | None:
        return self._states.get(entity_id)


class FakeHass:
    def __init__(self, states: dict[str, FakeState]) -> None:
        self.states = FakeStates(states)


def test_numeric_and_counter_normalization() -> None:
    assert normalize_numeric_state("12.5") == 12.5
    assert normalize_numeric_state("unknown") is None
    assert normalize_numeric_state("-") is None
    assert normalize_counter_state("3.9") == 3
    assert normalize_counter_state("-4") == 0


def test_build_lightning_snapshot_triggers_inside_radius() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    distance_state = {
        "entity_id": "sensor.home_lightning_distance",
        "state": "12.4",
        "last_updated": now - timedelta(seconds=45),
    }
    counter_state = {
        "entity_id": "sensor.home_lightning_counter",
        "state": "8",
        "last_updated": now - timedelta(seconds=30),
    }

    snapshot = build_lightning_snapshot(
        distance_state=distance_state,
        counter_state=counter_state,
        previous_counter=6,
        trigger_radius_km=30,
        stale_after_seconds=900,
        now=now,
    )

    assert snapshot.source_available is True
    assert snapshot.distance_km == 12.4
    assert snapshot.counter == 8
    assert snapshot.counter_delta == 2
    assert snapshot.has_new_strike is True
    assert snapshot.trigger_active is True
    assert snapshot.diagnostics == ()


def test_build_lightning_snapshot_marks_stale_source_and_suppresses_trigger() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    old = now - timedelta(seconds=901)

    snapshot = build_lightning_snapshot(
        distance_state={"state": "5", "last_updated": old},
        counter_state={"state": "10", "last_updated": now},
        previous_counter=10,
        trigger_radius_km=30,
        stale_after_seconds=900,
        now=now,
    )

    assert snapshot.source_available is True
    assert snapshot.is_stale is True
    assert snapshot.trigger_active is False
    assert "stale_distance_entity" in snapshot.diagnostics


def test_build_lightning_snapshot_reports_missing_and_invalid_entities() -> None:
    snapshot = build_lightning_snapshot(
        distance_state=None,
        counter_state={"state": "not-a-number"},
    )

    assert snapshot.source_available is False
    assert snapshot.trigger_active is False
    assert "missing_distance_entity" in snapshot.diagnostics
    assert "invalid_counter_state" in snapshot.diagnostics


def test_build_lightning_snapshot_treats_unknown_distance_as_empty_not_invalid() -> None:
    snapshot = build_lightning_snapshot(
        distance_state={"state": "unknown"},
        counter_state={"state": "0"},
    )

    assert snapshot.source_available is True
    assert snapshot.distance_km is None
    assert snapshot.counter == 0
    assert snapshot.trigger_active is False
    assert "invalid_distance_state" not in snapshot.diagnostics


def test_autodetect_blitzortung_entities_prefers_lightning_sensors() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    candidates = autodetect_blitzortung_entities(
        [
            FakeState(
                "sensor.home_temperature",
                "22",
                {"friendly_name": "Home temperature"},
                now,
            ),
            FakeState(
                "sensor.home_lightning_distance",
                "11",
                {"friendly_name": "Home Lightning Distance", "device_class": "distance"},
                now,
            ),
            FakeState(
                "sensor.home_lightning_counter",
                "3",
                {"friendly_name": "Home Lightning Counter"},
                now,
            ),
        ]
    )

    assert candidates.distance_entity_id == "sensor.home_lightning_distance"
    assert candidates.counter_entity_id == "sensor.home_lightning_counter"


def test_home_assistant_lightning_source_reads_and_tracks_previous_counter() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    source = HomeAssistantLightningSource(
        distance_entity_id="sensor.home_lightning_distance",
        counter_entity_id="sensor.home_lightning_counter",
        trigger_radius_km=30,
        stale_after_seconds=900,
    )
    hass = FakeHass(
        {
            "sensor.home_lightning_distance": FakeState(
                "sensor.home_lightning_distance",
                "9",
                {"friendly_name": "Home Lightning Distance"},
                now,
            ),
            "sensor.home_lightning_counter": FakeState(
                "sensor.home_lightning_counter",
                "4",
                {"friendly_name": "Home Lightning Counter"},
                now,
            ),
        }
    )

    first = source.read(hass, now=now)
    assert first.previous_counter is None
    assert first.counter == 4
    assert first.trigger_active is True

    hass.states._states["sensor.home_lightning_counter"].state = "6"
    second = source.read(hass, now=now + timedelta(seconds=10))
    assert second.previous_counter == 4
    assert second.counter == 6
    assert second.counter_delta == 2
