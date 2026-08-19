"""Blitzortung-compatible lightning source helpers.

The integration intentionally does not depend on Blitzortung internals.  It reads
Home Assistant entities that expose nearest-lightning distance and lightning
counter values, then normalizes them into a small snapshot the risk engine can
use as trigger/context.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def normalize_numeric_state(value: Any) -> float | None:
    """Parse HA sensor values to float when possible.

    Accepts ``None``, ``"unknown"``, and ``"unavailable"`` as invalid
    and returns ``None``.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"unknown", "unavailable", "none", "null", "-", ""}:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None

    return None


def is_empty_state(value: Any) -> bool:
    """Return true for normal HA empty states that should not be reported as errors."""

    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"unknown", "unavailable", "none", "null", "-", ""}
    return False


def is_unavailable_state(value: Any) -> bool:
    """Return true only when Home Assistant explicitly marks an entity unavailable."""

    return isinstance(value, str) and value.strip().lower() == "unavailable"


def normalize_counter_state(value: Any) -> int | None:
    """Normalize counter-like values to non-negative integers."""

    normalized = normalize_numeric_state(value)
    if normalized is None:
        return None
    integer = int(normalized)
    return max(integer, 0)


def normalize_azimuth_state(value: Any) -> float | None:
    """Normalize lightning azimuth/bearing to 0..360 degrees."""

    normalized = normalize_numeric_state(value)
    if normalized is None:
        return None
    return float(normalized % 360)


def destination_point(
    latitude: float, longitude: float, distance_km: float, bearing_degrees: float
) -> tuple[float, float]:
    """Project a point from lat/lon using distance and bearing."""

    radius_km = 6371.0088
    angular_distance = distance_km / radius_km
    bearing = math.radians(bearing_degrees)
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), ((math.degrees(lon2) + 540) % 360) - 180


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two lat/lon points in km."""

    radius_km = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True)
class LightningEntityCandidates:
    """Autodetected entity IDs for Blitzortung-compatible sources."""

    distance_entity_id: str | None = None
    counter_entity_id: str | None = None
    azimuth_entity_id: str | None = None


@dataclass(frozen=True)
class LightningSnapshot:
    """Normalized lightning state used by the storm evaluator."""

    distance_km: float | None
    counter: int | None
    azimuth_degrees: float | None = None
    previous_counter: int | None = None
    trigger_radius_km: float = 30.0
    source_available: bool = False
    is_stale: bool = False
    distance_age_seconds: int | None = None
    counter_age_seconds: int | None = None
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def counter_delta(self) -> int | None:
        """Return the non-negative counter delta when both values are known."""

        if self.counter is None:
            return None
        if self.previous_counter is None:
            return 0
        return max(self.counter - self.previous_counter, 0)

    @property
    def counter_reset(self) -> bool:
        """Return true when the source counter moved backwards."""

        return (
            self.counter is not None
            and self.previous_counter is not None
            and self.counter < self.previous_counter
        )

    @property
    def has_new_strike(self) -> bool:
        """Return true when a current counter advanced since the previous snapshot."""

        delta = self.counter_delta
        return (
            "stale_counter_entity" not in self.diagnostics
            and delta is not None
            and delta > 0
        )

    @property
    def proximity_active(self) -> bool:
        """Return true when the current distance is inside the configured radius."""

        return (
            self.source_available
            and "stale_distance_entity" not in self.diagnostics
            and self.distance_km is not None
            and self.distance_km <= self.trigger_radius_km
        )

    @property
    def new_strike_nearby(self) -> bool:
        """Return true only for a new counter event with current nearby distance."""

        return self.proximity_active and self.has_new_strike

    @property
    def trigger_active(self) -> bool:
        """Backward-compatible alias for the proximity state."""

        return self.proximity_active


def build_lightning_snapshot(
    *,
    distance_state: Any,
    counter_state: Any,
    azimuth_state: Any = None,
    previous_counter: int | None = None,
    trigger_radius_km: float = 30.0,
    stale_after_seconds: int = 900,
    now: datetime | None = None,
) -> LightningSnapshot:
    """Normalize HA distance/counter states into a lightning snapshot.

    ``distance_state`` and ``counter_state`` may be native Home Assistant State
    objects, dicts with ``state``/``last_updated`` fields, or raw scalar values
    for tests.
    """

    now = _coerce_aware_datetime(now or datetime.now(timezone.utc))
    diagnostics: list[str] = []

    if distance_state is None:
        diagnostics.append("missing_distance_entity")
    if counter_state is None:
        diagnostics.append("missing_counter_entity")

    raw_distance = _extract_state_value(distance_state)
    raw_counter = _extract_state_value(counter_state)
    raw_azimuth = _extract_state_value(azimuth_state)
    distance = normalize_numeric_state(raw_distance)
    counter = normalize_counter_state(raw_counter)
    azimuth = normalize_azimuth_state(raw_azimuth)

    if distance_state is not None and distance is None and not is_empty_state(raw_distance):
        diagnostics.append("invalid_distance_state")
    if counter_state is not None and counter is None and not is_empty_state(raw_counter):
        diagnostics.append("invalid_counter_state")
    if azimuth_state is not None and azimuth is None and not is_empty_state(raw_azimuth):
        diagnostics.append("invalid_azimuth_state")

    if distance_state is not None and is_unavailable_state(raw_distance):
        diagnostics.append("unavailable_distance_entity")
    if counter_state is not None and is_unavailable_state(raw_counter):
        diagnostics.append("unavailable_counter_entity")

    distance_age = _state_age_seconds(distance_state, now)
    counter_age = _state_age_seconds(counter_state, now)

    distance_stale = distance_age is not None and distance_age > stale_after_seconds
    counter_stale = counter_age is not None and counter_age > stale_after_seconds
    if distance_stale:
        diagnostics.append("stale_distance_entity")
    if counter_stale:
        diagnostics.append("stale_counter_entity")
    if counter is not None and previous_counter is not None and counter < previous_counter:
        diagnostics.append("lightning_counter_reset")

    source_available = (distance is not None or counter is not None) and not (
        distance_state is None and counter_state is None
    )

    # Distance and counter are event-driven values: their HA timestamps describe
    # the last lightning event, not a provider heartbeat. Keep age diagnostics to
    # suppress old event evidence, but never infer source health from inactivity.
    is_stale = False

    return LightningSnapshot(
        distance_km=distance,
        counter=counter,
        azimuth_degrees=azimuth,
        previous_counter=previous_counter,
        trigger_radius_km=trigger_radius_km,
        source_available=source_available,
        is_stale=is_stale,
        distance_age_seconds=distance_age,
        counter_age_seconds=counter_age,
        diagnostics=tuple(diagnostics),
    )


def autodetect_blitzortung_entities(states: Iterable[Any]) -> LightningEntityCandidates:
    """Best-effort autodetect of Blitzortung distance and counter entities.

    The function is conservative: it only returns sensors with names/entity IDs
    that look like lightning/Blitzortung sources. Users can still override the
    selected entities in the config flow.
    """

    distance: str | None = None
    counter: str | None = None
    azimuth: str | None = None

    for state in states:
        entity_id = _extract_entity_id(state)
        if not entity_id or not entity_id.startswith("sensor."):
            continue

        haystack = " ".join(
            part
            for part in (
                entity_id,
                str(_extract_attributes(state).get("friendly_name", "")),
                str(_extract_attributes(state).get("device_class", "")),
            )
            if part
        ).lower()

        looks_like_lightning = "lightning" in haystack or "blitzortung" in haystack
        if not looks_like_lightning:
            continue

        if distance is None and (
            "distance" in haystack
            or "vzdalen" in haystack
            or "vzdálen" in haystack
            or _extract_attributes(state).get("device_class") == "distance"
        ):
            distance = entity_id
            continue

        if counter is None and (
            "counter" in haystack
            or "count" in haystack
            or "strikes" in haystack
            or "blesk" in haystack
        ):
            counter = entity_id
            continue

        if azimuth is None and (
            "azimuth" in haystack or "bearing" in haystack or "direction" in haystack
        ):
            azimuth = entity_id

    return LightningEntityCandidates(
        distance_entity_id=distance,
        counter_entity_id=counter,
        azimuth_entity_id=azimuth,
    )


class HomeAssistantLightningSource:
    """Read Blitzortung-compatible lightning entities from Home Assistant."""

    def __init__(
        self,
        *,
        distance_entity_id: str,
        counter_entity_id: str,
        azimuth_entity_id: str | None = None,
        trigger_radius_km: float = 30.0,
        stale_after_seconds: int = 900,
    ) -> None:
        self.distance_entity_id = distance_entity_id
        self.counter_entity_id = counter_entity_id
        self.azimuth_entity_id = azimuth_entity_id
        self.trigger_radius_km = trigger_radius_km
        self.stale_after_seconds = stale_after_seconds
        self.previous_counter: int | None = None

    def read(self, hass: Any, *, now: datetime | None = None) -> LightningSnapshot:
        """Read current HA states and return a normalized snapshot."""

        states = getattr(hass, "states", None)
        getter = getattr(states, "get", None)
        if getter is None:
            snapshot = build_lightning_snapshot(
                distance_state=None,
                counter_state=None,
                azimuth_state=None,
                previous_counter=self.previous_counter,
                trigger_radius_km=self.trigger_radius_km,
                stale_after_seconds=self.stale_after_seconds,
                now=now,
            )
            return _with_extra_diagnostic(snapshot, "hass_states_unavailable")

        snapshot = build_lightning_snapshot(
            distance_state=getter(self.distance_entity_id),
            counter_state=getter(self.counter_entity_id),
            azimuth_state=getter(self.azimuth_entity_id) if self.azimuth_entity_id else None,
            previous_counter=self.previous_counter,
            trigger_radius_km=self.trigger_radius_km,
            stale_after_seconds=self.stale_after_seconds,
            now=now,
        )
        if snapshot.counter is not None:
            self.previous_counter = snapshot.counter
        return snapshot


def _with_extra_diagnostic(snapshot: LightningSnapshot, diagnostic: str) -> LightningSnapshot:
    return LightningSnapshot(
        distance_km=snapshot.distance_km,
        counter=snapshot.counter,
        azimuth_degrees=snapshot.azimuth_degrees,
        previous_counter=snapshot.previous_counter,
        trigger_radius_km=snapshot.trigger_radius_km,
        source_available=snapshot.source_available,
        is_stale=snapshot.is_stale,
        distance_age_seconds=snapshot.distance_age_seconds,
        counter_age_seconds=snapshot.counter_age_seconds,
        diagnostics=(*snapshot.diagnostics, diagnostic),
    )


def _extract_state_value(state: Any) -> Any:
    if state is None:
        return None
    if isinstance(state, dict):
        return state.get("state")
    return getattr(state, "state", state)


def _extract_entity_id(state: Any) -> str | None:
    if isinstance(state, dict):
        entity_id = state.get("entity_id")
    else:
        entity_id = getattr(state, "entity_id", None)
    return entity_id if isinstance(entity_id, str) else None


def _extract_attributes(state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        attributes = state.get("attributes", {})
    else:
        attributes = getattr(state, "attributes", {})
    return attributes if isinstance(attributes, dict) else {}


def _state_age_seconds(state: Any, now: datetime) -> int | None:
    timestamp = _extract_timestamp(state)
    if timestamp is None:
        return None
    age = now - timestamp
    return max(int(age.total_seconds()), 0)


def _extract_timestamp(state: Any) -> datetime | None:
    if state is None:
        return None
    timestamp: Any
    if isinstance(state, dict):
        timestamp = state.get("last_updated") or state.get("last_reported")
    else:
        timestamp = getattr(state, "last_updated", None) or getattr(state, "last_reported", None)
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(timestamp, datetime):
        return _coerce_aware_datetime(timestamp)
    return None


def _coerce_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
