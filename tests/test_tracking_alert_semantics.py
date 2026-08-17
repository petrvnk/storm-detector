"""Sequence tests for storm tracking and alert semantics hardening."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.storm_detector.binary_sensor import RadarHailRiskActiveBinarySensor
from custom_components.storm_detector.const import (
    EVIDENCE_KIND_LIGHTNING_ONLY,
    EVIDENCE_KIND_NONE,
    EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING,
    RISK_LEVEL_URGENT,
    RISK_LEVEL_WARNING,
)
from custom_components.storm_detector.rainviewer import AnalyzedFrame, _motion_from_frame_results
from custom_components.storm_detector.risk import (
    RiskLevelHysteresis,
    classify_from_thresholds,
    evidence_kind_for_levels,
)


def _frame(
    *,
    frame_time: int,
    selected_distance_km: float,
    selected_latitude: float,
    selected_longitude: float,
    selected_max_dbz: int,
    storm_cores: tuple[dict[str, int | float], ...],
    selected_threshold_dbz: int = 50,
) -> AnalyzedFrame:
    return AnalyzedFrame(
        frame_time=frame_time,
        max_dbz=selected_max_dbz,
        max_core_dbz=selected_max_dbz,
        core50_distance_km=selected_distance_km,
        core55_distance_km=selected_distance_km,
        core60_distance_km=selected_distance_km,
        core_watch_distance_km=selected_distance_km,
        core_warning_distance_km=selected_distance_km,
        core_urgent_distance_km=selected_distance_km,
        core50_latitude=selected_latitude,
        core50_longitude=selected_longitude,
        core55_latitude=selected_latitude,
        core55_longitude=selected_longitude,
        core60_latitude=selected_latitude,
        core60_longitude=selected_longitude,
        core_watch_latitude=selected_latitude,
        core_watch_longitude=selected_longitude,
        core_warning_latitude=selected_latitude,
        core_warning_longitude=selected_longitude,
        core_urgent_latitude=selected_latitude,
        core_urgent_longitude=selected_longitude,
        selected_core_area_km2=1.0,
        selected_core_pixel_count=4,
        selected_core_max_dbz=selected_max_dbz,
        selected_core_threshold_dbz=selected_threshold_dbz,
        selected_core_distance_km=selected_distance_km,
        selected_core_latitude=selected_latitude,
        selected_core_longitude=selected_longitude,
        selected_core_centroid_latitude=selected_latitude,
        selected_core_centroid_longitude=selected_longitude,
        storm_cores=storm_cores,
        core_count=len(storm_cores),
        analyzed_pixels=20,
    )


def _core(
    *,
    distance_km: float,
    latitude: float,
    longitude: float,
    max_dbz: int,
) -> dict[str, int | float]:
    return {
        "threshold_dbz": 50,
        "max_dbz": max_dbz,
        "distance_km": distance_km,
        "latitude": latitude,
        "longitude": longitude,
        "centroid_latitude": latitude,
        "centroid_longitude": longitude,
        "pixel_count": 4,
        "area_km2": 1.0,
    }


def test_motion_tracks_same_intensity_core_through_crossing_and_uses_radial_eta() -> None:
    latest = _frame(
        frame_time=2_000,
        selected_distance_km=10.0,
        selected_latitude=0.09,
        selected_longitude=0.09,
        selected_max_dbz=62,
        storm_cores=(
            _core(distance_km=10.0, latitude=0.09, longitude=0.09, max_dbz=62),
            _core(distance_km=9.0, latitude=0.08, longitude=0.08, max_dbz=51),
        ),
    )
    older = _frame(
        frame_time=1_400,
        selected_distance_km=9.0,
        selected_latitude=0.08,
        selected_longitude=0.08,
        selected_max_dbz=51,
        storm_cores=(
            _core(distance_km=20.0, latitude=0.18, longitude=0.0, max_dbz=60),
            _core(distance_km=9.0, latitude=0.08, longitude=0.08, max_dbz=51),
        ),
    )

    motion = _motion_from_frame_results([latest, older])

    assert motion.speed_kmh is not None
    assert motion.speed_kmh > 80
    assert motion.approaching is True
    assert motion.eta_minutes == 10
    assert motion.dbz_trend == "stable"
    assert motion.distance_trend == "approaching"


def test_motion_rejects_matches_that_require_implausible_storm_speed() -> None:
    latest = _frame(
        frame_time=2_000,
        selected_distance_km=10.0,
        selected_latitude=0.01,
        selected_longitude=0.0,
        selected_max_dbz=60,
        storm_cores=(
            _core(distance_km=10.0, latitude=0.01, longitude=0.0, max_dbz=60),
        ),
    )
    older = _frame(
        frame_time=1_400,
        selected_distance_km=200.0,
        selected_latitude=2.0,
        selected_longitude=0.0,
        selected_max_dbz=60,
        storm_cores=(
            _core(distance_km=200.0, latitude=2.0, longitude=0.0, max_dbz=60),
        ),
    )

    motion = _motion_from_frame_results([latest, older])

    assert motion.speed_kmh is None
    assert motion.eta_minutes is None
    assert motion.approaching is None


def test_motion_uses_selected_urgent_core_when_omitted_from_watch_summaries() -> None:
    closer_watch_cores = tuple(
        _core(
            distance_km=float(index),
            latitude=index / 100,
            longitude=0.0,
            max_dbz=50,
        )
        for index in range(1, 9)
    )
    latest = _frame(
        frame_time=2_000,
        selected_distance_km=20.0,
        selected_latitude=0.18,
        selected_longitude=0.0,
        selected_max_dbz=62,
        storm_cores=closer_watch_cores,
        selected_threshold_dbz=60,
    )
    older = _frame(
        frame_time=1_400,
        selected_distance_km=30.0,
        selected_latitude=0.27,
        selected_longitude=0.0,
        selected_max_dbz=61,
        storm_cores=closer_watch_cores,
        selected_threshold_dbz=60,
    )

    motion = _motion_from_frame_results([latest, older])

    assert motion.speed_kmh is not None
    assert 55 < motion.speed_kmh < 65
    assert motion.approaching is True
    assert motion.eta_minutes == 20


def test_motion_does_not_claim_approach_for_slow_radial_drift() -> None:
    latest = _frame(
        frame_time=2_000,
        selected_distance_km=77.0,
        selected_latitude=0.69,
        selected_longitude=0.10,
        selected_max_dbz=46,
        storm_cores=(
            _core(distance_km=77.0, latitude=0.69, longitude=0.10, max_dbz=46),
        ),
        selected_threshold_dbz=45,
    )
    older = _frame(
        frame_time=1_400,
        selected_distance_km=78.0,
        selected_latitude=0.70,
        selected_longitude=-0.10,
        selected_max_dbz=46,
        storm_cores=(
            _core(distance_km=78.0, latitude=0.70, longitude=-0.10, max_dbz=46),
        ),
        selected_threshold_dbz=45,
    )

    motion = _motion_from_frame_results([latest, older])

    assert motion.speed_kmh is not None
    assert motion.speed_kmh > 100
    assert motion.approaching is False
    assert motion.eta_minutes is None
    assert motion.distance_trend == "stable"


def test_lightning_only_new_nearby_strike_is_capped_at_warning() -> None:
    inputs = {
        "max_dbz": None,
        "core_distance_km": None,
        "lightning_distance_km": 4.0,
        "watch_dbz": 50,
        "warning_dbz": 55,
        "urgent_dbz": 60,
        "warning_core_distance_km": 25,
        "urgent_core_distance_km": 15,
        "warning_lightning_distance_km": 20,
        "urgent_lightning_distance_km": 8,
        "lightning_triggered": True,
        "lightning_counter_delta": 0,
    }

    assert (
        classify_from_thresholds(**inputs, lightning_new_strike=False) == RISK_LEVEL_WARNING
    )
    assert (
        classify_from_thresholds(
            **{**inputs, "lightning_counter_delta": 1}, lightning_new_strike=True
        )
        == RISK_LEVEL_WARNING
    )


def test_radar_urgent_core_with_new_lightning_remains_urgent() -> None:
    assert (
        classify_from_thresholds(
            max_dbz=62,
            core_distance_km=None,
            lightning_distance_km=4.0,
            watch_dbz=50,
            warning_dbz=55,
            urgent_dbz=60,
            warning_core_distance_km=25,
            urgent_core_distance_km=15,
            warning_lightning_distance_km=20,
            urgent_lightning_distance_km=8,
            lightning_triggered=True,
            lightning_counter_delta=1,
            lightning_new_strike=True,
            core50_distance_km=4.0,
            core55_distance_km=4.0,
            core60_distance_km=4.0,
        )
        == RISK_LEVEL_URGENT
    )


def test_evidence_kind_describes_published_level_without_pending_overclaim() -> None:
    assert (
        evidence_kind_for_levels(
            level="none", radar_level="warning", lightning_level="unavailable"
        )
        == EVIDENCE_KIND_NONE
    )
    assert (
        evidence_kind_for_levels(
            level="warning", radar_level="unavailable", lightning_level="warning"
        )
        == EVIDENCE_KIND_LIGHTNING_ONLY
    )
    assert (
        evidence_kind_for_levels(
            level="warning", radar_level="warning", lightning_level="warning"
        )
        == EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING
    )


def test_risk_hysteresis_confirms_escalation_and_clearing_without_flapping() -> None:
    state = RiskLevelHysteresis(confirmations=2)

    assert state.update("none") == "none"
    assert state.update("warning") == "none"
    assert state.update("none") == "none"
    assert state.update("warning") == "none"
    assert state.update("warning") == "warning"
    assert state.update("none") == "warning"
    assert state.update("warning") == "warning"
    assert state.update("none") == "warning"
    assert state.update("none") == "none"
    assert state.update("urgent", force=True) == "urgent"


def test_risk_hysteresis_publishes_first_valid_level_after_startup_unavailable() -> None:
    state = RiskLevelHysteresis(confirmations=2)

    assert state.update("unavailable", force=True) == "unavailable"
    assert state.update("warning") == "warning"


def test_active_sensor_requires_a_current_contributing_signal() -> None:
    coordinator = SimpleNamespace(
        data={"level": RISK_LEVEL_WARNING, "has_current_signal": False}
    )
    sensor = RadarHailRiskActiveBinarySensor(coordinator)
    sensor._coordinator = coordinator

    assert sensor.is_on is False

    coordinator.data["has_current_signal"] = True
    assert sensor.is_on is True
