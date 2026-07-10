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
        "lightning_counter_reset",
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


class RiskLevelHysteresis:
    """Confirm level changes while emitting one stable deduplicated state."""

    def __init__(self, *, confirmations: int = 2) -> None:
        self.confirmations = max(1, int(confirmations))
        self._stable: RiskLevel | None = None
        self._initialized_valid = False
        self._pending: RiskLevel | None = None
        self._pending_count = 0

    def update(self, candidate: RiskLevel, *, force: bool = False) -> RiskLevel:
        """Return the stable level after applying confirmation semantics."""

        if candidate == "unavailable" or force:
            self._stable = candidate
            if candidate != "unavailable":
                self._initialized_valid = True
            self._pending = None
            self._pending_count = 0
            return candidate
        if not self._initialized_valid:
            self._stable = candidate
            self._initialized_valid = True
            self._pending = None
            self._pending_count = 0
            return candidate
        assert self._stable is not None
        if candidate == self._stable:
            self._pending = None
            self._pending_count = 0
            return self._stable
        if candidate == self._pending:
            self._pending_count += 1
        else:
            self._pending = candidate
            self._pending_count = 1
        if self._pending_count >= self.confirmations:
            self._stable = candidate
            self._pending = None
            self._pending_count = 0
        return self._stable


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
    core_watch_distance_km: float | None = None
    core_warning_distance_km: float | None = None
    core_urgent_distance_km: float | None = None
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
    storm_cores: tuple[dict[str, Any], ...] = ()
    core_count: int | None = None
    selected_core_latitude: float | None = None
    selected_core_longitude: float | None = None
    storm_motion_bearing: float | None = None
    storm_motion_speed_kmh: float | None = None
    storm_approaching: bool | None = None
    storm_eta_minutes: int | None = None
    dbz_trend: str | None = None
    distance_trend: str | None = None
    confidence_score: int | None = None
    confidence_level: str | None = None
    frames_analyzed: int | None = None
    frame_time: int | None = None
    last_error: str | None = None
    is_stale: bool = False
    has_lightning_trigger: bool = False
    has_lightning_new_strike: bool = False
    lightning_counter_delta: int | None = None
    has_current_signal: bool = False
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
    lightning_new_strike: bool = False,
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
        lightning_new_strike
        and lightning_triggered
        and lightning_distance_km is not None
        and lightning_distance_km <= warning_lightning_distance_km
    ):
        # A new nearby strike is event evidence; proximity by itself remains warning.
        if (
            lightning_distance_km is not None
            and lightning_distance_km <= urgent_lightning_distance_km
            and (lightning_counter_delta or 0) > 0
        ):
            return RISK_LEVEL_URGENT
        return RISK_LEVEL_WARNING

    if core60_distance_km is not None and core60_distance_km <= urgent_core_distance_km:
        return RISK_LEVEL_URGENT

    if core60_distance_km is not None and core60_distance_km <= warning_core_distance_km:
        return RISK_LEVEL_WARNING
    if core55_distance_km is not None and core55_distance_km <= warning_core_distance_km:
        return RISK_LEVEL_WARNING
    if lightning_distance_km is not None and lightning_distance_km <= warning_lightning_distance_km:
        return RISK_LEVEL_WARNING
    if (
        max_dbz is not None
        and max_dbz >= urgent_dbz
        and core50_distance_km is not None
        and core50_distance_km <= urgent_core_distance_km
    ):
        # RainViewer's discrete color table can split compact hail cores: the nearest
        # 50+ dBZ edge may be overhead while the nearest 55+/60+ connected component
        # is just outside the strict warning radius. Do not leave a high-reflectivity
        # storm overhead as WATCH only.
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
