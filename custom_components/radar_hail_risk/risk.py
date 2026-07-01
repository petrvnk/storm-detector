"""Risk model contracts and threshold classifier for radar + lightning risk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .const import (
    RISK_LEVEL_NONE,
    RISK_LEVEL_URGENT,
    RISK_LEVEL_WARNING,
    RISK_LEVEL_WATCH,
)

RiskLevel = Literal["none", "watch", "warning", "urgent", "unavailable"]

# Internal event markers are useful as attributes for debugging but should never leak
# into the human-facing summary or last_error sensor. They are not source failures.
INTERNAL_EVENT_DIAGNOSTICS = frozenset(
    {
        "lightning_strike_delta",
        "lightning_counter_delta",
        "lightning_not_configured",
    }
)


def user_visible_diagnostics(diagnostics: tuple[str, ...]) -> tuple[str, ...]:
    """Return diagnostics that are safe to show in user-facing text.

    The coordinator keeps detailed radar/lightning diagnostics as attributes. This
    helper prevents internal event/debug markers from becoming scary alert text like
    ``Warning (lightning_strike_delta)``.
    """

    return tuple(
        diagnostic for diagnostic in diagnostics if diagnostic not in INTERNAL_EVENT_DIAGNOSTICS
    )


@dataclass(frozen=True)
class HailRiskResult:
    """Structured risk output contract used by the coordinator entities."""

    level: RiskLevel
    summary: str
    max_dbz: int | None = None
    core_distance_km: float | None = None
    core50_distance_km: float | None = None
    core55_distance_km: float | None = None
    core60_distance_km: float | None = None
    lightning_distance_km: float | None = None
    lightning_azimuth_degrees: float | None = None
    lightning_latitude: float | None = None
    lightning_longitude: float | None = None
    lightning_core_distance_km: float | None = None
    frame_age_seconds: int | None = None
    selected_core_threshold_dbz: int | None = None
    selected_core_distance_km: float | None = None
    selected_core_area_km2: float | None = None
    selected_core_pixel_count: int | None = None
    selected_core_max_dbz: int | None = None
    core_count: int | None = None
    selected_core_latitude: float | None = None
    selected_core_longitude: float | None = None
    storm_motion_bearing: float | None = None
    storm_motion_speed_kmh: float | None = None
    storm_approaching: bool | None = None
    storm_eta_minutes: int | None = None
    dbz_trend: str | None = None
    distance_trend: str | None = None
    frames_analyzed: int | None = None
    frame_time: int | None = None
    last_error: str | None = None
    is_stale: bool = False
    has_lightning_trigger: bool = False
    lightning_counter_delta: int | None = None
    diagnostics: tuple[str, ...] = ()


def classify_from_thresholds(
    *,
    max_dbz: int | None,
    core_distance_km: float | None,
    lightning_distance_km: float | None,
    watch_dbz: int,
    warning_dbz: int,
    urgent_dbz: int,
    warning_core_distance_km: int,
    urgent_core_distance_km: int,
    warning_lightning_distance_km: int,
    urgent_lightning_distance_km: int,
    lightning_triggered: bool | None = None,
    lightning_counter_delta: int | None = None,
    core50_distance_km: float | None = None,
    core55_distance_km: float | None = None,
    core60_distance_km: float | None = None,
) -> RiskLevel:
    """Classify current risk level from staged thresholds.

    The function intentionally keeps all inputs explicit so the integration can evolve
    risk heuristics without changing the call shape.  Radar core distance is
    threshold-aware: 50+ dBZ cores can only create WATCH, 55+ nearby cores create
    WARNING, and only 60+ nearby cores can create URGENT.
    """

    core50_distance_km = core50_distance_km if core50_distance_km is not None else core_distance_km
    if max_dbz is None and core50_distance_km is None and lightning_distance_km is None:
        return "unavailable"

    if (
        lightning_triggered
        and lightning_distance_km is not None
        and lightning_distance_km <= warning_lightning_distance_km
    ):
        # Explicit trigger is user-visible and should always surface as at least warning.
        if (
            lightning_distance_km is not None
            and lightning_distance_km <= urgent_lightning_distance_km
            and (lightning_counter_delta or 0) > 0
        ):
            return RISK_LEVEL_URGENT
        return RISK_LEVEL_WARNING

    if core60_distance_km is not None and core60_distance_km <= urgent_core_distance_km:
        return RISK_LEVEL_URGENT
    if lightning_distance_km is not None and lightning_distance_km <= urgent_lightning_distance_km:
        return RISK_LEVEL_URGENT

    if core60_distance_km is not None and core60_distance_km <= warning_core_distance_km:
        return RISK_LEVEL_WARNING
    if core55_distance_km is not None and core55_distance_km <= warning_core_distance_km:
        return RISK_LEVEL_WARNING
    if lightning_distance_km is not None and lightning_distance_km <= warning_lightning_distance_km:
        return RISK_LEVEL_WARNING

    if core60_distance_km is not None or core55_distance_km is not None:
        return RISK_LEVEL_WATCH
    if core50_distance_km is not None:
        return RISK_LEVEL_WATCH
    if max_dbz is not None and max_dbz >= watch_dbz:
        return RISK_LEVEL_WATCH

    # For live UX, a strong thunderstorm just below the hail-core watch threshold
    # should not be rendered as a green OK state. RainViewer/Windy dBZ estimates can
    # differ by a few dBZ and the current frame can fluctuate quickly around the
    # threshold. Keep warning/urgent strict, but surface near-threshold cores as watch.
    near_watch_dbz = max(0, watch_dbz - 5)
    if max_dbz is not None and max_dbz > near_watch_dbz:
        return RISK_LEVEL_WATCH

    return RISK_LEVEL_NONE


def build_summary(
    *,
    level: RiskLevel,
    max_dbz: int | None,
    core_distance_km: float | None,
    lightning_distance_km: float | None,
    frame_age_seconds: int | None,
    selected_core_threshold_dbz: int | None,
    diagnostics: tuple[str, ...] = (),
) -> str:
    """Build a short user-facing summary for the main risk sensor."""

    public_diagnostics = user_visible_diagnostics(diagnostics)
    if public_diagnostics:
        suffix = f" ({', '.join(public_diagnostics)})"
    else:
        suffix = ""

    if level == "unavailable":
        return f"Risk unavailable{suffix}"

    if level == "none":
        if max_dbz is None and frame_age_seconds is not None:
            return "Radar available: no threshold risk detected" + suffix
        if max_dbz is None:
            return "No radar cores detected" + suffix
        if selected_core_threshold_dbz is None or core_distance_km is None:
            return f"Max dBZ {max_dbz} with low risk" + suffix
        return (
            f"Max dBZ {max_dbz}, closest core: {selected_core_threshold_dbz}+{core_distance_km:.1f} km"
            + suffix
        )

    if level == "watch":
        return f"Watch: max {max_dbz if max_dbz is not None else 'n/a'} dBZ" + suffix
    if level == "warning":
        return (
            "Warning: "
            + (f"max {max_dbz if max_dbz is not None else 'n/a'} dBZ" if max_dbz is not None else "core risk")
            + suffix
        )
    return "Urgent risk" + suffix


def normalize_optional_int(value: Any, *, default: int) -> int:
    """Parse int-like values while preserving defaults for invalid values."""

    try:
        if isinstance(value, bool):
            return int(value)
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def normalize_optional_float(value: Any, *, default: float) -> float:
    """Parse float-like values while preserving defaults for invalid values."""

    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default
