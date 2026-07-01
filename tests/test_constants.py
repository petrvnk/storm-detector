"""Tests for options defaults and required constants used by Stage 2."""

from __future__ import annotations

from custom_components.radar_hail_risk.const import (
    CONF_ANALYSIS_RADIUS_KM,
    DATA_KEY_RESULT,
    DEFAULT_ANALYSIS_RADIUS_KM,
    DEFAULT_CORE_WARNING_DBZ,
    DEFAULT_URGENT_CORE_DISTANCE_KM,
    DOMAIN,
    OPTIONAL_CONF_DEFAULTS,
    PARAMETER_SPECS,
    PLATFORMS,
)


def test_constants_default_contract() -> None:
    assert DOMAIN == "radar_hail_risk"
    assert DEFAULT_ANALYSIS_RADIUS_KM == 50
    assert DEFAULT_CORE_WARNING_DBZ == 55
    assert DEFAULT_URGENT_CORE_DISTANCE_KM == 15
    assert CONF_ANALYSIS_RADIUS_KM in OPTIONAL_CONF_DEFAULTS
    assert set(PARAMETER_SPECS) == set(OPTIONAL_CONF_DEFAULTS)
    assert PARAMETER_SPECS[CONF_ANALYSIS_RADIUS_KM]["unit"] == "km"
    assert DATA_KEY_RESULT == "hail_risk_result"
    assert "sensor" in PLATFORMS
