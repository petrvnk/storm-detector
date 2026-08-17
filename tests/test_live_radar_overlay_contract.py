"""Focused backend contract tests for the synchronized live radar overlay."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from custom_components.storm_detector.const import (
    ATTR_RADAR_OVERLAY,
    ATTR_STORM_CORES,
    DEFAULT_STALE_CLEAR_SECONDS,
)
from custom_components.storm_detector.coordinator import (
    RadarHailRiskCoordinator,
    _build_radar_overlay,
)
from custom_components.storm_detector.rainviewer import (
    _analyse_dbz_grid,
    analyze_recent_frames,
    build_rainviewer_tile_url_template,
)
from custom_components.storm_detector.sensor import (
    RadarHailRiskLevelSensor,
    RadarHailRiskSummarySensor,
)


class _FakeHass:
    def __init__(self) -> None:
        self.config = SimpleNamespace(latitude=50.0755, longitude=14.4378)
        self.states = SimpleNamespace(get=lambda _entity_id: None, async_all=lambda: [])


class _FakeSessionContext:
    async def __aenter__(self) -> "_FakeSessionContext":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeEntry:
    entry_id = "entry-live-overlay"
    data: dict[str, object] = {}
    options: dict[str, object] = {}


def _current_analysis(*, frame_age_seconds: int = 120) -> SimpleNamespace:
    return SimpleNamespace(
        max_dbz=57,
        max_core_dbz=57,
        core50_distance_km=6.23456789,
        core55_distance_km=6.23456789,
        core60_distance_km=None,
        core_watch_distance_km=6.23456789,
        core_warning_distance_km=6.23456789,
        core_urgent_distance_km=None,
        selected_core_threshold_dbz=55,
        selected_core_distance_km=6.23456789,
        selected_core_latitude=50.10000049,
        selected_core_longitude=14.50000049,
        selected_core_centroid_latitude=50.10200049,
        selected_core_centroid_longitude=14.50300049,
        selected_core_area_km2=3.25,
        selected_core_pixel_count=4,
        selected_core_max_dbz=57,
        storm_cores=(
            {
                "index": 1,
                "threshold_dbz": 50,
                "max_dbz": 57,
                "distance_km": 6.23456789,
                "bearing_degrees": 37.5,
                "latitude": 50.10000049,
                "longitude": 14.50000049,
                "centroid_latitude": 50.10200049,
                "centroid_longitude": 14.50300049,
                "area_km2": 3.25,
                "pixel_count": 4,
            },
            {
                "index": 2,
                "threshold_dbz": 50,
                "max_dbz": 52,
                "distance_km": 18.4,
                "bearing_degrees": 210.0,
                "latitude": 49.92,
                "longitude": 14.39,
                "centroid_latitude": 49.918,
                "centroid_longitude": 14.386,
                "area_km2": 1.5,
                "pixel_count": 2,
            },
        ),
        core_count=2,
        storm_motion_bearing=None,
        storm_motion_speed_kmh=None,
        storm_approaching=None,
        storm_eta_minutes=None,
        dbz_trend=None,
        distance_trend=None,
        frame_age_seconds=frame_age_seconds,
        frame_time=1_710_000_000,
        frame_host="https://tilecache.rainviewer.com",
        frame_path="/v2/radar/1710000000",
        metadata_generated_time=1_710_000_060,
        tile_size=512,
        display_zoom=7,
        max_native_zoom=7,
        color_scheme_id=2,
        tile_options="1_1",
        frames_analyzed=2,
    )


async def _coordinator_payload(
    analysis: Any, *, has_color_lookup: bool = True
) -> tuple[RadarHailRiskCoordinator, dict]:
    async def _fake_meta(*_args: object, **_kwargs: object) -> dict:
        return {
            "generated": 1_710_000_060,
            "host": "https://tilecache.rainviewer.com",
            "radar": {
                "past": [
                    {"time": 1_710_000_000, "path": "/v2/radar/1710000000"}
                ]
            },
        }

    async def _fake_color(*_args: object, **_kwargs: object) -> dict:
        return {(255, 0, 0, 255): 57} if has_color_lookup else {}

    with patch(
        "custom_components.storm_detector.coordinator.fetch_radar_metadata", _fake_meta
    ), patch(
        "custom_components.storm_detector.coordinator.fetch_rainviewer_color_lookup",
        _fake_color,
    ), patch(
        "custom_components.storm_detector.coordinator.analyze_recent_frames",
        lambda *_args, **_kwargs: analysis,
    ):
        coordinator = RadarHailRiskCoordinator(
            _FakeHass(),
            None,
            "Storm Detector",
            _FakeEntry(),
            session_factory=_FakeSessionContext,
        )
        payload = await coordinator._async_update_data()
    return coordinator, payload


async def _aggregate_frame(frame: Any) -> Any:
    metadata = {
        "generated": frame.frame_time + 60,
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [{"time": frame.frame_time, "path": frame.frame_path}]
        },
    }
    with patch(
        "custom_components.storm_detector.rainviewer.analyze_single_radar_frame",
        AsyncMock(return_value=frame),
    ):
        analysis = await analyze_recent_frames(
            object(),
            metadata,
            center_latitude=50.0,
            center_longitude=14.4,
            analysis_radius_km=80.0,
            required_frames=1,
            color_lookup={(255, 0, 0, 255): 62},
            now=frame.frame_time + 120,
        )
    assert analysis is not None
    return analysis


async def test_current_radar_overlay_is_synchronized_selected_and_json_safe() -> None:
    coordinator, payload = await _coordinator_payload(_current_analysis())

    overlay = payload[ATTR_RADAR_OVERLAY]
    assert overlay["schema_version"] == 1
    assert overlay["status"] == "ok"
    assert overlay["provider"] == "RainViewer"
    assert overlay["mode"] == "rainviewer_tile_mosaic"
    assert overlay["attribution"] == {
        "label": "Weather data by RainViewer",
        "url": "https://www.rainviewer.com/",
    }

    frame = overlay["frame"]
    assert frame["time"] == payload["frame_time"] == 1_710_000_000
    assert frame["age_seconds"] == payload["frame_age_seconds"] == 120
    assert frame["generated_time"] == 1_710_000_060
    assert frame["tile_size"] == 512
    assert frame["display_zoom"] == frame["max_native_zoom"] == 7
    assert frame["tile_url_template"].startswith("https://")
    assert set(re.findall(r"\{[^}]+\}", frame["tile_url_template"])) == {
        "{z}",
        "{x}",
        "{y}",
    }

    assert overlay["viewport"] == {
        "center_latitude": 50.0755,
        "center_longitude": 14.4378,
        "location_source": "hass.config",
        "radius_km": 80.0,
        "warning_radius_km": 25,
        "urgent_radius_km": 15,
    }
    assert overlay["thresholds"] == {
        "near_watch_dbz": 45,
        "watch_dbz": 50,
        "warning_dbz": 55,
        "urgent_dbz": 60,
        "min_core_pixels": 2,
    }

    assert overlay["cores"]
    assert all(core["frame_time"] == frame["time"] for core in overlay["cores"])
    selected = [core for core in overlay["cores"] if core["selected"]]
    assert len(selected) == 1
    assert overlay["selected_core_id"] == selected[0]["id"]
    assert selected[0]["role"] == "risk_driver"
    assert selected[0]["risk_band"] == "warning"
    assert selected[0]["threshold_dbz"] == payload["selected_core_threshold_dbz"]
    assert selected[0]["max_dbz"] == payload["selected_core_max_dbz"]
    assert selected[0]["distance_km"] == payload["selected_core_distance_km"]
    assert selected[0]["latitude"] == payload["selected_core_latitude"]
    assert selected[0]["longitude"] == payload["selected_core_longitude"]
    assert selected[0]["render_latitude"] == selected[0]["centroid_latitude"]
    assert selected[0]["render_longitude"] == selected[0]["centroid_longitude"]

    assert isinstance(payload["storm_cores"], list)
    assert len(json.dumps(overlay)) < 16 * 1024

    coordinator.data = payload
    sensor = RadarHailRiskLevelSensor(coordinator, _FakeEntry())
    sensor._coordinator = coordinator
    assert sensor.extra_state_attributes[ATTR_RADAR_OVERLAY] == overlay


async def test_radar_overlay_is_exposed_only_on_level_sensor() -> None:
    coordinator, payload = await _coordinator_payload(_current_analysis())
    coordinator.data = payload

    level_sensor = RadarHailRiskLevelSensor(coordinator, _FakeEntry())
    summary_sensor = RadarHailRiskSummarySensor(coordinator, _FakeEntry())

    assert ATTR_RADAR_OVERLAY in level_sensor.extra_state_attributes
    assert ATTR_RADAR_OVERLAY not in summary_sensor.extra_state_attributes


async def test_secondary_core_risk_bands_use_intensity_and_distance_gates() -> None:
    frame_time = 1_710_000_000
    points = {
        (index * 3, 0): (
            62,
            50.0 + index / 1000,
            14.4 + index / 1000,
            distance_km,
        )
        for index, distance_km in ((1, 5.0), (2, 10.0), (3, 20.0), (4, 30.0))
    }
    frame = _analyse_dbz_grid(
        points,
        center_latitude=50.0,
        center_longitude=14.4,
        zoom=7,
        tile_size=512,
        frame_time=frame_time,
        frame_path="/v2/radar/1710000000",
        core_watch_dbz=50,
        core_warning_dbz=55,
        core_urgent_dbz=60,
    )
    analysis = await _aggregate_frame(frame)

    _, payload = await _coordinator_payload(analysis)
    cores_by_index = {
        core["index"]: core for core in payload[ATTR_RADAR_OVERLAY]["cores"]
    }

    assert cores_by_index[2]["risk_band"] == "urgent"
    assert cores_by_index[3]["risk_band"] == "warning"
    assert cores_by_index[4]["risk_band"] == "watch"


async def test_connected_threshold_subcore_stays_one_selected_overlay_core() -> None:
    frame_time = 1_710_000_000
    frame = _analyse_dbz_grid(
        {
            (0, 0): (50, 50.0, 14.400, 5.0),
            (1, 0): (50, 50.0, 14.410, 10.0),
            (2, 0): (62, 50.0, 14.420, 30.0),
        },
        center_latitude=50.0,
        center_longitude=14.4,
        zoom=7,
        tile_size=512,
        frame_time=frame_time,
        frame_path="/v2/radar/1710000000",
        core_watch_dbz=50,
        core_warning_dbz=55,
        core_urgent_dbz=60,
    )
    analysis = await _aggregate_frame(frame)

    _, payload = await _coordinator_payload(analysis)
    overlay = payload[ATTR_RADAR_OVERLAY]
    selected = [core for core in overlay["cores"] if core["selected"]]

    assert payload["core_count"] == overlay["limits"]["core_count_total"] == 1
    assert len(overlay["cores"]) == 1
    assert len(selected) == 1
    assert overlay["selected_core_id"] == selected[0]["id"]
    assert selected[0]["risk_band"] == payload["level"] == "warning"
    assert selected[0]["threshold_dbz"] == payload["selected_core_threshold_dbz"]
    assert selected[0]["distance_km"] == payload["selected_core_distance_km"]
    assert selected[0]["latitude"] == payload["selected_core_latitude"]
    assert selected[0]["longitude"] == payload["selected_core_longitude"]


async def test_connected_selected_component_is_forced_inside_real_analysis_cap() -> None:
    frame_time = 1_710_000_000
    points = {
        (index * 4, 0): (
            50,
            50.0 + index / 1000,
            14.4 + index / 1000,
            float(index),
        )
        for index in range(1, 14)
    }
    points[(13 * 4 + 1, 0)] = (62, 50.02, 14.42, 30.0)
    frame = _analyse_dbz_grid(
        points,
        center_latitude=50.0,
        center_longitude=14.4,
        zoom=7,
        tile_size=512,
        frame_time=frame_time,
        frame_path="/v2/radar/1710000000",
        core_watch_dbz=50,
        core_warning_dbz=55,
        core_urgent_dbz=60,
    )

    assert frame.core_count == 13
    assert len(frame.overlay_cores) == 12
    assert frame.overlay_selected_core_forced_included is True
    assert any(core["index"] == 13 for core in frame.overlay_cores)

    analysis = await _aggregate_frame(frame)
    _, payload = await _coordinator_payload(analysis)
    overlay = payload[ATTR_RADAR_OVERLAY]

    assert overlay["limits"]["core_count_total"] == payload["core_count"] == 13
    assert overlay["limits"]["selected_core_forced_included"] is True
    assert len(overlay["cores"]) == len({core["id"] for core in overlay["cores"]}) == 12
    assert sum(core["selected"] for core in overlay["cores"]) == 1
    assert overlay["selected_core_id"] == f"{frame_time}:core:13"


async def test_stale_radar_overlay_fails_closed_without_frame_or_cores() -> None:
    _, payload = await _coordinator_payload(
        _current_analysis(frame_age_seconds=DEFAULT_STALE_CLEAR_SECONDS + 1)
    )

    overlay = payload[ATTR_RADAR_OVERLAY]
    assert overlay["status"] == "stale"
    assert overlay["frame"] is None
    assert overlay["selected_core_id"] is None
    assert overlay["cores"] == []
    assert payload["selected_core_distance_km"] is None
    assert payload["storm_cores"] == []


async def test_missing_analysis_overlay_fails_closed_as_degraded() -> None:
    _, payload = await _coordinator_payload(None)

    overlay = payload[ATTR_RADAR_OVERLAY]
    assert overlay["status"] == "degraded"
    assert overlay["frame"] is None
    assert overlay["cores"] == []
    assert "tile_url_template" not in json.dumps(overlay)


async def test_missing_frame_contract_or_color_lookup_fails_closed() -> None:
    missing_host = _current_analysis()
    missing_host.frame_host = None
    _, host_payload = await _coordinator_payload(missing_host)

    missing_path = _current_analysis()
    missing_path.frame_path = None
    _, path_payload = await _coordinator_payload(missing_path)

    _, color_payload = await _coordinator_payload(
        _current_analysis(), has_color_lookup=False
    )

    invalid_selected_core = _current_analysis()
    invalid_selected_core.selected_core_latitude = "not-a-latitude"
    _, invalid_payload = await _coordinator_payload(invalid_selected_core)

    for payload in (host_payload, path_payload, color_payload, invalid_payload):
        overlay = payload[ATTR_RADAR_OVERLAY]
        assert overlay["status"] == "degraded"
        assert overlay["frame"] is None
        assert overlay["cores"] == []


def test_tile_url_template_rejects_untrusted_or_ambiguous_inputs() -> None:
    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com/",
        "v2/radar/1710000000/",
    ) == (
        "https://tilecache.rainviewer.com/v2/radar/1710000000/"
        "512/{z}/{x}/{y}/2/1_1.png"
    )
    assert build_rainviewer_tile_url_template(
        "http://tilecache.rainviewer.com", "/v2/radar/1710000000"
    ) is None
    assert build_rainviewer_tile_url_template(
        "https://user@example.com", "/v2/radar/1710000000"
    ) is None
    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com", "/v2/radar/{frame}"
    ) is None
    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com", "/v2/radar/frame?redirect=1"
    ) is None
    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com", "/v2/radar/frame\n"
    ) is None


def test_tile_url_template_accepts_current_opaque_frame_id() -> None:
    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com",
        "/v2/radar/f606500dfba7",
    ) == (
        "https://tilecache.rainviewer.com/v2/radar/f606500dfba7/"
        "512/{z}/{x}/{y}/2/1_1.png"
    )

    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com",
        "/v2/radar/f_60650-dfba7",
    ) == (
        "https://tilecache.rainviewer.com/v2/radar/f_60650-dfba7/"
        "512/{z}/{x}/{y}/2/1_1.png"
    )


def test_tile_url_template_rejects_overlong_rainviewer_frame_id() -> None:
    assert build_rainviewer_tile_url_template(
        "https://tilecache.rainviewer.com",
        "/v2/radar/" + "f" * 1024,
    ) is None


def test_tile_url_template_rejects_malformed_rainviewer_dns_labels() -> None:
    for host in (
        "https://.rainviewer.com",
        "https://evil..rainviewer.com",
        "https://-edge.rainviewer.com",
        "https://edge-.rainviewer.com",
    ):
        assert build_rainviewer_tile_url_template(
            host,
            "/v2/radar/f606500dfba7",
        ) is None


def test_tile_url_template_rejects_oversized_components() -> None:
    host = "https://tilecache.rainviewer.com"

    assert build_rainviewer_tile_url_template(
        host,
        f"/v2/radar/{'a' * 65}",
    ) is None
    assert build_rainviewer_tile_url_template(
        host,
        "/v2/radar/f606500dfba7",
        options="bad-value",
    ) is None


def test_tile_url_template_rejects_non_rainviewer_hosts_and_malformed_paths() -> None:
    invalid_inputs = (
        ("https://example.com", "/v2/radar/1710000000"),
        ("https://tilecache.rainviewer.com.evil.example", "/v2/radar/1710000000"),
        ("https://tilecache.rainviewer.com", "/not-radar/1710000000"),
        ("https://tilecache.rainviewer.com", "/v2/radar/not.a-frame"),
        ("https://tilecache.rainviewer.com", "//evil.example/v2/radar/1710000000"),
        ("https://tilecache.rainviewer.com", "/v2/radar/1710000000%0aevil"),
    )

    for host, path in invalid_inputs:
        assert build_rainviewer_tile_url_template(host, path) is None


async def test_selected_core_is_forced_inside_render_cap() -> None:
    analysis = _current_analysis()
    cores = []
    for index in range(1, 14):
        cores.append(
            {
                "index": index,
                "threshold_dbz": 50,
                "max_dbz": 50 + (index % 5),
                "distance_km": float(index),
                "bearing_degrees": float(index * 10),
                "latitude": 49.9 + index / 1000,
                "longitude": 14.3 + index / 1000,
                "centroid_latitude": 49.9005 + index / 1000,
                "centroid_longitude": 14.3005 + index / 1000,
                "area_km2": float(index),
                "pixel_count": index,
            }
        )
    selected = cores[-1]
    analysis.storm_cores = tuple(cores)
    analysis.core_count = len(cores)
    analysis.selected_core_threshold_dbz = 55
    analysis.selected_core_distance_km = selected["distance_km"]
    analysis.selected_core_latitude = selected["latitude"]
    analysis.selected_core_longitude = selected["longitude"]
    analysis.selected_core_centroid_latitude = selected["centroid_latitude"]
    analysis.selected_core_centroid_longitude = selected["centroid_longitude"]
    analysis.selected_core_max_dbz = 57
    analysis.selected_core_area_km2 = selected["area_km2"]
    analysis.selected_core_pixel_count = selected["pixel_count"]
    analysis.display_zoom = 9
    analysis.max_native_zoom = 9

    _, payload = await _coordinator_payload(analysis)
    overlay = payload[ATTR_RADAR_OVERLAY]

    assert overlay["status"] == "ok"
    assert len(overlay["cores"]) == 12
    assert overlay["limits"] == {
        "core_count_total": 13,
        "core_count_rendered": 12,
        "core_limit": 12,
        "selected_core_forced_included": True,
    }
    assert overlay["selected_core_id"] in {core["id"] for core in overlay["cores"]}
    assert sum(core["selected"] for core in overlay["cores"]) == 1
    assert overlay["frame"]["display_zoom"] == 7
    assert overlay["frame"]["max_native_zoom"] == 7
    assert len(json.dumps(overlay)) < 16 * 1024


async def test_typical_radar_overlay_payload_stays_below_ten_kilobytes() -> None:
    _, payload = await _coordinator_payload(_current_analysis())

    encoded = json.dumps(payload[ATTR_RADAR_OVERLAY], separators=(",", ":")).encode()

    assert len(encoded) < 10 * 1024


def test_oversized_radar_overlay_payload_fails_closed() -> None:
    analysis = _current_analysis()
    long_template = "https://tilecache.rainviewer.com/" + "x" * 25000

    with patch(
        "custom_components.storm_detector.coordinator.build_rainviewer_tile_url_template",
        return_value=long_template,
    ):
        overlay = _build_radar_overlay(
            analysis,
            radar_status="ok",
            radar_stale=False,
            frame_age_seconds=120,
            center_latitude=50.0,
            center_longitude=14.0,
            location_source="gps",
            analysis_radius_km=80.0,
            warning_radius_km=25,
            urgent_radius_km=15,
            watch_dbz=50,
            warning_dbz=55,
            urgent_dbz=60,
            min_core_pixels=2,
        )

    assert overlay["status"] == "degraded"
    assert overlay["frame"] is None
    assert overlay["cores"] == []
    assert overlay["selected_core_id"] is None
    serialized = json.dumps(overlay, separators=(",", ":")).encode()
    assert b"tile_url_template" not in serialized
    assert len(serialized) <= 16 * 1024


def test_fail_closed_overlay_itself_stays_within_hard_budget() -> None:
    overlay = _build_radar_overlay(
        _current_analysis(),
        radar_status="ok",
        radar_stale=False,
        frame_age_seconds=120,
        center_latitude=50.0,
        center_longitude=14.0,
        location_source="x" * 20000,
        analysis_radius_km=80.0,
        warning_radius_km=25,
        urgent_radius_km=15,
        watch_dbz=50,
        warning_dbz=55,
        urgent_dbz=60,
        min_core_pixels=2,
    )

    serialized = json.dumps(overlay, separators=(",", ":")).encode()
    assert overlay["status"] == "degraded"
    assert overlay["frame"] is None
    assert overlay["cores"] == []
    assert len(serialized) <= 16 * 1024


async def test_real_analysis_pipeline_keeps_twelve_overlay_cores_and_selected() -> None:
    frame_time = 1_710_000_000
    points = {
        (index * 3, 0): (
            62 if index == 13 else 50,
            50.0 + index / 1000,
            14.4 + index / 1000,
            float(index),
        )
        for index in range(1, 14)
    }
    frame = _analyse_dbz_grid(
        points,
        center_latitude=50.0,
        center_longitude=14.4,
        zoom=7,
        tile_size=512,
        frame_time=frame_time,
        frame_path="/v2/radar/1710000000",
        core_watch_dbz=50,
        core_warning_dbz=55,
        core_urgent_dbz=60,
    )
    analysis = await _aggregate_frame(frame)

    assert analysis.core_count == 13
    assert len(analysis.storm_cores) == 8

    _, payload = await _coordinator_payload(analysis)
    overlay = payload[ATTR_RADAR_OVERLAY]

    assert len(overlay["cores"]) == 12
    assert overlay["limits"]["core_count_total"] == 13
    assert overlay["limits"]["selected_core_forced_included"] is True
    assert overlay["selected_core_id"] in {core["id"] for core in overlay["cores"]}
    assert sum(core["selected"] for core in overlay["cores"]) == 1


async def test_radar_overlay_payload_is_json_serializable() -> None:
    coordinator, payload = await _coordinator_payload(_current_analysis())

    coordinator.data = payload
    level_sensor = RadarHailRiskLevelSensor(coordinator, _FakeEntry())
    payload_json = json.dumps(payload, sort_keys=True)

    assert json.loads(payload_json)[ATTR_RADAR_OVERLAY] == payload[ATTR_RADAR_OVERLAY]
    assert json.loads(json.dumps(level_sensor.extra_state_attributes[ATTR_RADAR_OVERLAY]))[
        "status"
    ] == "ok"


async def test_current_overlay_uses_normalized_tile_host_path_and_zoom_caps() -> None:
    analysis = _current_analysis()
    analysis.display_zoom = 13
    analysis.max_native_zoom = 9
    analysis.color_scheme_id = 4
    analysis.tile_options = "2_2"
    analysis.frame_path = "v2/radar/f606500dfba7/"
    analysis.frame_host = "https://tilecache.rainviewer.com:443/"

    _, payload = await _coordinator_payload(analysis)
    overlay = payload[ATTR_RADAR_OVERLAY]
    frame = overlay["frame"]

    assert overlay["status"] == "ok"
    assert frame["tile_url_template"] == (
        "https://tilecache.rainviewer.com:443/v2/radar/f606500dfba7/"
        "512/{z}/{x}/{y}/4/2_2.png"
    )
    assert frame["tile_size"] == 512
    assert frame["max_native_zoom"] == 7
    assert frame["display_zoom"] == 7


async def test_overlay_cores_conform_to_contract_and_selection_is_consistent() -> None:
    _, payload = await _coordinator_payload(_current_analysis())
    overlay = payload[ATTR_RADAR_OVERLAY]
    frame_time = overlay["frame"]["time"]

    required_core_fields = {
        "id",
        "frame_time",
        "index",
        "selected",
        "role",
        "risk_band",
        "threshold_dbz",
        "max_dbz",
        "distance_km",
        "bearing_degrees",
        "latitude",
        "longitude",
        "centroid_latitude",
        "centroid_longitude",
        "render_latitude",
        "render_longitude",
        "area_km2",
        "pixel_count",
    }
    assert overlay["selected_core_id"]
    assert len([core for core in overlay["cores"] if core["selected"]]) == 1

    for core in overlay["cores"]:
        assert required_core_fields <= core.keys()
        assert core["id"].startswith(f"{frame_time}:core:")
        assert core["frame_time"] == frame_time

    selected_id = overlay["selected_core_id"]
    selected = next(core for core in overlay["cores"] if core["id"] == selected_id)
    assert selected["selected"] is True
    assert selected["role"] == "risk_driver"

    assert payload[ATTR_STORM_CORES]
    storm = payload[ATTR_STORM_CORES][0]
    overlay_match = next(
        core for core in overlay["cores"] if core["index"] == storm["index"]
    )
    assert overlay_match["index"] == storm["index"]


def test_unavailable_and_stale_overlays_do_not_carry_tile_templates() -> None:
    stale = _build_radar_overlay(
        None,
        radar_status="ok",
        radar_stale=True,
        frame_age_seconds=10,
        center_latitude=50.0,
        center_longitude=14.0,
        location_source="hass.config",
        analysis_radius_km=80.0,
        warning_radius_km=25,
        urgent_radius_km=15,
        watch_dbz=50,
        warning_dbz=55,
        urgent_dbz=60,
        min_core_pixels=2,
    )

    unavailable = _build_radar_overlay(
        None,
        radar_status="ok",
        radar_stale=False,
        frame_age_seconds=10,
        center_latitude=50.0,
        center_longitude=14.0,
        location_source="hass.config",
        analysis_radius_km=80.0,
        warning_radius_km=25,
        urgent_radius_km=15,
        watch_dbz=50,
        warning_dbz=55,
        urgent_dbz=60,
        min_core_pixels=2,
    )

    for overlay in (stale, unavailable):
        assert overlay["frame"] is None
        assert overlay["cores"] == []
        assert "tile_url_template" not in json.dumps(overlay)
