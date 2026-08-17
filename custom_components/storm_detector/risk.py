"""Risk model contracts and threshold classifier for radar + lightning risk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .const import (
    EVIDENCE_KIND_LIGHTNING_ONLY,
    EVIDENCE_KIND_NONE,
    EVIDENCE_KIND_RADAR_HAIL,
    EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING,
    EVIDENCE_KIND_RADAR_STORM,
    EVIDENCE_KIND_UNAVAILABLE,
    RISK_LEVEL_NONE,
    RISK_LEVEL_URGENT,
    RISK_LEVEL_WARNING,
    RISK_LEVEL_WATCH,
)

RiskLevel = Literal["none", "watch", "warning", "urgent", "unavailable"]
EvidenceKind = Literal[
    "none",
    "radar_storm",
    "radar_hail",
    "lightning_only",
    "radar_hail_with_lightning",
    "unavailable",
]

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
class StormRiskResult:
    """Structured risk output contract used by the coordinator entities."""

    level: RiskLevel
    summary: str
    evidence_kind: EvidenceKind
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

    if core60_distance_km is not None and core60_distance_km <= urgent_core_distance_km:
        return RISK_LEVEL_URGENT

    if (
        lightning_new_strike
        and lightning_triggered
        and lightning_distance_km is not None
        and lightning_distance_km <= warning_lightning_distance_km
    ):
        # Lightning can force immediate publication, but without current urgent radar
        # evidence it is storm context rather than a hail-urgent signal.
        return RISK_LEVEL_WARNING

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
    evidence_kind: EvidenceKind,
    max_dbz: int | None,
    core_distance_km: float | None,
    lightning_distance_km: float | None,
    frame_age_seconds: int | None,
    selected_core_threshold_dbz: int | None,
    diagnostics: tuple[str, ...] = (),
) -> str:
    """Build a short user-facing summary for the main risk sensor."""

    if level == "unavailable":
        return "Risk unavailable"

    if evidence_kind == EVIDENCE_KIND_LIGHTNING_ONLY:
        return "Thunderstorm / lightning nearby"

    if evidence_kind in {EVIDENCE_KIND_RADAR_HAIL, EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING}:
        if level == RISK_LEVEL_URGENT:
            summary = "High hail risk nearby"
        else:
            summary = "Possible hail nearby"
        if evidence_kind == EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING:
            summary += "; lightning also detected"
        return summary

    if evidence_kind == EVIDENCE_KIND_RADAR_STORM:
        return "Storm activity detected nearby"

    if level == "none":
        return "No strong radar core detected nearby"

    return "No current warning evidence; previous level awaiting confirmation"


def evidence_kind_for_levels(
    *, level: RiskLevel, radar_level: RiskLevel, lightning_level: RiskLevel
) -> EvidenceKind:
    """Return the stable machine-readable evidence discriminator for a payload."""

    if level == "unavailable":
        return EVIDENCE_KIND_UNAVAILABLE
    if level == RISK_LEVEL_NONE:
        return EVIDENCE_KIND_NONE
    if level == RISK_LEVEL_WATCH:
        return (
            EVIDENCE_KIND_RADAR_STORM
            if radar_level in {RISK_LEVEL_WATCH, RISK_LEVEL_WARNING, RISK_LEVEL_URGENT}
            else EVIDENCE_KIND_NONE
        )
    if level == RISK_LEVEL_URGENT and radar_level != RISK_LEVEL_URGENT:
        return EVIDENCE_KIND_NONE

    has_radar_hail = radar_level in {RISK_LEVEL_WARNING, RISK_LEVEL_URGENT}
    has_lightning = lightning_level == RISK_LEVEL_WARNING
    if has_radar_hail and has_lightning:
        return EVIDENCE_KIND_RADAR_HAIL_WITH_LIGHTNING
    if has_radar_hail:
        return EVIDENCE_KIND_RADAR_HAIL
    if has_lightning:
        return EVIDENCE_KIND_LIGHTNING_ONLY
    if radar_level == RISK_LEVEL_WATCH:
        return EVIDENCE_KIND_RADAR_STORM
    return EVIDENCE_KIND_NONE


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
