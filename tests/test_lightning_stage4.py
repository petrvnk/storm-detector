"""Tests for Blitzortung-compatible lightning source helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from custom_components.storm_detector.lightning import (
    HomeAssistantLightningSource,
    autodetect_blitzortung_entities,
    build_lightning_snapshot,
    destination_point,
    haversine_km,
    normalize_azimuth_state,
    normalize_counter_state,
    normalize_numeric_state,
)

UTC = timezone.utc


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
    assert normalize_azimuth_state("370") == 10


def test_destination_point_projects_lightning_bearing() -> None:
    lat, lon = destination_point(50.0, 14.0, 10.0, 90.0)

    assert haversine_km(50.0, 14.0, lat, lon) == pytest.approx(10.0, abs=0.01)
    assert lon > 14.0


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
        azimuth_state={"state": "90", "last_updated": now - timedelta(seconds=15)},
        previous_counter=6,
        trigger_radius_km=30,
        stale_after_seconds=900,
        now=now,
    )

    assert snapshot.source_available is True
    assert snapshot.distance_km == 12.4
    assert snapshot.counter == 8
    assert snapshot.azimuth_degrees == 90
    assert snapshot.counter_delta == 2
    assert snapshot.has_new_strike is True
    assert snapshot.trigger_active is True
    assert snapshot.diagnostics == ()


def test_build_lightning_snapshot_suppresses_old_event_without_staling_source() -> None:
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
    assert snapshot.is_stale is False
    assert snapshot.trigger_active is False
    assert "stale_distance_entity" in snapshot.diagnostics


def test_no_lightning_activity_does_not_stale_event_driven_source() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    old = now - timedelta(hours=8)

    snapshot = build_lightning_snapshot(
        distance_state={"state": "unknown", "last_updated": old},
        counter_state={"state": "0", "last_updated": old},
        previous_counter=0,
        stale_after_seconds=900,
        now=now,
    )

    assert snapshot.source_available is True
    assert snapshot.distance_km is None
    assert snapshot.counter == 0
    assert snapshot.counter_delta == 0
    assert snapshot.is_stale is False
    assert snapshot.trigger_active is False
    assert snapshot.has_new_strike is False
    assert "stale_distance_entity" in snapshot.diagnostics
    assert "stale_counter_entity" in snapshot.diagnostics


def test_unavailable_lightning_entity_is_reported_as_source_failure() -> None:
    snapshot = build_lightning_snapshot(
        distance_state={"state": "unavailable"},
        counter_state={"state": "0"},
    )

    assert snapshot.source_available is True
    assert "unavailable_distance_entity" in snapshot.diagnostics


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
            FakeState(
                "sensor.home_lightning_azimuth",
                "90",
                {"friendly_name": "Home Lightning Azimuth"},
                now,
            ),
        ]
    )

    assert candidates.distance_entity_id == "sensor.home_lightning_distance"
    assert candidates.counter_entity_id == "sensor.home_lightning_counter"
    assert candidates.azimuth_entity_id == "sensor.home_lightning_azimuth"


def test_home_assistant_lightning_source_reads_and_tracks_previous_counter() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    source = HomeAssistantLightningSource(
        distance_entity_id="sensor.home_lightning_distance",
        counter_entity_id="sensor.home_lightning_counter",
        azimuth_entity_id="sensor.home_lightning_azimuth",
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
            "sensor.home_lightning_azimuth": FakeState(
                "sensor.home_lightning_azimuth",
                "180",
                {"friendly_name": "Home Lightning Azimuth"},
                now,
            ),
        }
    )

    first = source.read(hass, now=now)
    assert first.previous_counter is None
    assert first.counter == 4
    assert first.azimuth_degrees == 180
    assert first.trigger_active is True

    hass.states._states["sensor.home_lightning_counter"].state = "6"
    second = source.read(hass, now=now + timedelta(seconds=10))
    assert second.previous_counter == 4
    assert second.counter == 6
    assert second.counter_delta == 2


def test_lightning_snapshot_keeps_fresh_proximity_when_counter_is_stale() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    snapshot = build_lightning_snapshot(
        distance_state=FakeState("sensor.distance", "5", {}, now),
        counter_state=FakeState(
            "sensor.counter", "10", {}, now - timedelta(seconds=1_000)
        ),
        previous_counter=9,
        trigger_radius_km=30,
        stale_after_seconds=900,
        now=now,
    )

    assert snapshot.is_stale is False
    assert snapshot.proximity_active is True
    assert snapshot.has_new_strike is False
    assert snapshot.new_strike_nearby is False


def test_lightning_source_separates_proximity_new_strikes_and_counter_resets() -> None:
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
                "sensor.home_lightning_distance", "4", {}, now
            ),
            "sensor.home_lightning_counter": FakeState(
                "sensor.home_lightning_counter", "10", {}, now
            ),
        }
    )

    first = source.read(hass, now=now)
    assert first.proximity_active is True
    assert first.new_strike_nearby is False
    assert first.counter_reset is False

    hass.states._states["sensor.home_lightning_counter"].state = "2"
    reset = source.read(hass, now=now + timedelta(seconds=10))
    assert reset.counter_delta == 0
    assert reset.counter_reset is True
    assert reset.new_strike_nearby is False
    assert "lightning_counter_reset" in reset.diagnostics

    hass.states._states["sensor.home_lightning_counter"].state = "3"
    after_reset = source.read(hass, now=now + timedelta(seconds=20))
    assert after_reset.counter_delta == 1
    assert after_reset.counter_reset is False
    assert after_reset.new_strike_nearby is True
