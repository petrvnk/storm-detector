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


@dataclass(frozen=True)
class HailRiskResult:
    """Structured risk output contract used by the coordinator entities."""

    level: RiskLevel
    summary: str
    max_dbz: int | None = None
    core_distance_km: float | None = None
    lightning_distance_km: float | None = None
    frame_age_seconds: int | None = None
    selected_core_threshold_dbz: int | None = None
    selected_core_distance_km: float | None = None
    selected_core_latitude: float | None = None
    selected_core_longitude: float | None = None
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
) -> RiskLevel:
    """Classify current risk level from staged thresholds.

    The function intentionally keeps all inputs explicit so the integration can evolve
    risk heuristics without changing the call shape.
    """

    if max_dbz is None and core_distance_km is None and lightning_distance_km is None:
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

    if max_dbz is not None and max_dbz >= urgent_dbz:
        return RISK_LEVEL_URGENT
    if core_distance_km is not None and core_distance_km <= urgent_core_distance_km:
        return RISK_LEVEL_URGENT
    if lightning_distance_km is not None and lightning_distance_km <= urgent_lightning_distance_km:
        return RISK_LEVEL_URGENT

    if max_dbz is not None and max_dbz >= warning_dbz:
        return RISK_LEVEL_WARNING
    if core_distance_km is not None and core_distance_km <= warning_core_distance_km:
        return RISK_LEVEL_WARNING
    if lightning_distance_km is not None and lightning_distance_km <= warning_lightning_distance_km:
        return RISK_LEVEL_WARNING

    if max_dbz is not None and max_dbz >= watch_dbz:
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

    if diagnostics:
        suffix = f" ({', '.join(diagnostics)})"
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
