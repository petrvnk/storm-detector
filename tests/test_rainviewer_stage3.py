"""Stage 3 radar-ingestion tests for RainViewer helpers."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any

import pytest
from custom_components.storm_detector.rainviewer import (
    AnalyzedFrame,
    _decode_dbz_grid,
    analyze_recent_frames,
    analyze_single_radar_frame,
    dbz_from_color_value,
    fetch_radar_metadata,
    global_px_to_latlon,
    latlon_to_global_px,
    parse_color_table,
    select_recent_frames,
)
from PIL import Image


@dataclass
class FakeResponse:
    status: int
    json_payload: Any | None = None
    text_payload: str | None = None
    bytes_payload: bytes | None = None

    async def json(self, content_type: str | None = None) -> Any:
        return self.json_payload

    async def text(self) -> str:
        assert self.text_payload is not None
        return self.text_payload

    async def read(self) -> bytes:
        if self.bytes_payload is not None:
            return self.bytes_payload
        if self.text_payload is not None:
            return self.text_payload.encode("utf-8")
        return (
            json.dumps(self.json_payload).encode("utf-8")
            if self.json_payload is not None
            else b"{}"
        )

    async def release(self) -> None:
        return None


class FakeSession:
    def __init__(self, route_map: dict[str, FakeResponse]):
        self.route_map = route_map
        self.requests: list[str] = []

    async def get(self, url: str, timeout: int = 20) -> FakeResponse:
        self.requests.append(url)
        return self.route_map.get(url, FakeResponse(404))


def test_select_recent_frames_sorts_and_filters() -> None:
    metadata = {
        "radar": {
            "past": [
                {"time": "100", "path": "A"},
                {"time": 300, "path": "B"},
                {"path": "missing-time"},
                {"time": 200, "path": "C"},
            ]
        }
    }

    selected = select_recent_frames(metadata, required_frames=2)
    assert selected == [
        {"time": 300, "path": "B"},
        {"time": 200, "path": "C"},
    ]


def test_parse_color_table_parses_rows() -> None:
    csv_text = (
        "dBZ / RGBA,Black and White,Original,Universal Blue\n"
        "-32,#00000000,#00000000,#00000000\n"
        "55,#00000000,#00000000,#ff0000ff\n"
        "60,#00000000,#00000000,#00ff00ff\n"
    )

    lookup = parse_color_table(csv_text)
    assert lookup[(255, 0, 0, 255)] == 55
    assert lookup[(0, 255, 0, 255)] == 60


def test_dbz_from_color_value_uses_lookup_for_rgba_and_hex() -> None:
    lookup = {(1, 2, 3, 255): 42, (170, 187, 204, 255): 55}

    assert dbz_from_color_value((1, 2, 3, 255), lookup) == 42
    assert dbz_from_color_value("#aabbccff", lookup) == 55
    assert dbz_from_color_value("not-a-color", lookup) is None


@pytest.mark.asyncio
async def test_fetch_radar_metadata_tries_fallback_endpoint() -> None:
    good_payload = {
        "radar": {"past": []},
        "host": "https://tilecache.rainviewer.com",
        "generated": 1,
    }
    session = FakeSession(
        {
            "https://fake/weather-maps-api/v1/radar": FakeResponse(404),
            "https://fake/weather-maps.json": FakeResponse(200, json_payload=good_payload),
        }
    )

    payload = await fetch_radar_metadata(session, api_base="https://fake", ttl_seconds=1)

    assert payload == good_payload
    assert session.requests == [
        "https://fake/weather-maps-api/v1/radar",
        "https://fake/weather-maps.json",
    ]


def _mk_radar_tile(
    size: int,
    color_map: dict[tuple[int, int, int, int], int],
    target: tuple[int, int],
    value: int,
) -> bytes:
    color = None
    for key, dbz in color_map.items():
        if dbz == value:
            color = key
            break
    assert color is not None

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.putpixel(target, color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_decode_dbz_grid_maps_colored_pixels() -> None:
    lookup = {(10, 20, 30, 255): 55}
    img = Image.new("RGBA", (3, 2), (0, 0, 0, 0))
    img.putpixel((2, 1), (10, 20, 30, 255))

    payload = io.BytesIO()
    img.save(payload, format="PNG")

    dbz_grid = _decode_dbz_grid(payload.getvalue(), lookup)
    assert dbz_grid[1][2] == 55
    assert dbz_grid[0][0] is None


@pytest.mark.asyncio
async def test_analyze_single_frame_detects_core_near_center() -> None:
    center_lat, center_lon = global_px_to_latlon(10000.4, 10000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    px_int = int(px)
    py_int = int(py)
    local_x = px_int % 512
    local_y = py_int % 512

    zoom = 7
    host = "https://tilecache.rainviewer.com"
    path = "/path"
    tx0 = px_int // 512
    ty0 = py_int // 512

    lookup = {(255, 0, 0, 255): 60}
    tile_url = f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png"
    tile = _mk_radar_tile(512, lookup, (local_x, local_y), 60)
    session = FakeSession({tile_url: FakeResponse(200, bytes_payload=tile)})

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.frame_time == 123
    assert frame_result.max_dbz == 60
    assert frame_result.core60_distance_km is not None
    assert frame_result.core60_distance_km <= 20
    assert frame_result.selected_core_pixel_count == 1
    assert frame_result.selected_core_max_dbz == 60
    assert frame_result.core_count == 1


@pytest.mark.asyncio
async def test_analyze_single_frame_detects_connected_near_watch_storm() -> None:
    center_lat, center_lon = global_px_to_latlon(10000.4, 10000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    px_int = int(px)
    py_int = int(py)
    local_x = px_int % 512
    local_y = py_int % 512

    zoom = 7
    host = "https://tilecache.rainviewer.com"
    path = "/near-watch"
    tx0 = px_int // 512
    ty0 = py_int // 512

    lookup = {(255, 165, 0, 255): 48}
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    img.putpixel((local_x, local_y), (255, 165, 0, 255))
    img.putpixel((local_x + 1, local_y), (255, 165, 0, 255))
    payload = io.BytesIO()
    img.save(payload, format="PNG")
    tile_url = f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png"
    session = FakeSession({tile_url: FakeResponse(200, bytes_payload=payload.getvalue())})

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
        core_watch_dbz=50,
        min_core_pixels=2,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.max_dbz == 48
    assert frame_result.max_core_dbz == 48
    assert frame_result.selected_core_threshold_dbz == 45
    assert frame_result.core_watch_distance_km is not None
    assert frame_result.core50_distance_km is None
    assert frame_result.selected_core_pixel_count == 2


@pytest.mark.asyncio
async def test_analyze_single_frame_uses_configured_near_watch_band() -> None:
    center_lat, center_lon = global_px_to_latlon(10000.4, 10000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    px_int = int(px)
    py_int = int(py)
    local_x = px_int % 512
    local_y = py_int % 512

    zoom = 7
    host = "https://tilecache.rainviewer.com"
    path = "/thresholds"
    tx0 = px_int // 512
    ty0 = py_int // 512

    lookup = {(255, 0, 0, 255): 58}
    tile_url = f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png"
    tile = _mk_radar_tile(512, lookup, (local_x, local_y), 58)
    session = FakeSession({tile_url: FakeResponse(200, bytes_payload=tile)})

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
        core_watch_dbz=60,
        core_warning_dbz=65,
        core_urgent_dbz=70,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.max_dbz == 58
    assert frame_result.max_core_dbz == 58
    assert frame_result.selected_core_threshold_dbz == 55
    assert frame_result.selected_core_distance_km is not None
    assert frame_result.core_watch_distance_km is not None
    assert frame_result.core_warning_distance_km is None
    assert frame_result.core_urgent_distance_km is None
    assert frame_result.core50_distance_km is not None
    assert frame_result.core55_distance_km is not None
    assert frame_result.core60_distance_km is None


@pytest.mark.asyncio
async def test_analyze_single_frame_clusters_connected_core_pixels() -> None:
    center_lat, center_lon = global_px_to_latlon(10000.4, 10000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    px_int = int(px)
    py_int = int(py)
    local_x = px_int % 512
    local_y = py_int % 512

    zoom = 7
    host = "https://tilecache.rainviewer.com"
    path = "/cluster"
    tx0 = px_int // 512
    ty0 = py_int // 512

    lookup = {(255, 0, 0, 255): 60}
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    img.putpixel((local_x, local_y), (255, 0, 0, 255))
    img.putpixel((local_x + 1, local_y), (255, 0, 0, 255))
    payload = io.BytesIO()
    img.save(payload, format="PNG")
    tile_url = f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png"
    session = FakeSession({tile_url: FakeResponse(200, bytes_payload=payload.getvalue())})

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
    )

    assert frame_result is not None
    assert frame_result.selected_core_pixel_count == 2
    assert frame_result.selected_core_area_km2 is not None
    assert frame_result.selected_core_area_km2 > 0
    assert frame_result.core_count == 1


@pytest.mark.asyncio
async def test_analyze_single_frame_rejects_single_pixel_noise_with_min_core_pixels() -> None:
    center_lat, center_lon = global_px_to_latlon(10000.4, 10000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    px_int = int(px)
    py_int = int(py)
    local_x = px_int % 512
    local_y = py_int % 512

    zoom = 7
    host = "https://tilecache.rainviewer.com"
    path = "/noise"
    tx0 = px_int // 512
    ty0 = py_int // 512

    lookup = {(255, 0, 0, 255): 62}
    tile = _mk_radar_tile(512, lookup, (local_x, local_y), 62)
    tile_url = f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png"
    session = FakeSession({tile_url: FakeResponse(200, bytes_payload=tile)})

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
        min_core_pixels=2,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.max_dbz == 62
    assert frame_result.selected_core_threshold_dbz is None
    assert frame_result.selected_core_pixel_count is None
    assert frame_result.core_count == 0


@pytest.mark.asyncio
async def test_analyze_single_frame_counts_separate_core_components() -> None:
    center_lat, center_lon = global_px_to_latlon(10000.4, 10000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    px_int = int(px)
    py_int = int(py)
    local_x = px_int % 512
    local_y = py_int % 512

    zoom = 7
    host = "https://tilecache.rainviewer.com"
    path = "/multi-core"
    tx0 = px_int // 512
    ty0 = py_int // 512

    lookup = {(255, 0, 0, 255): 60}
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    img.putpixel((local_x, local_y), (255, 0, 0, 255))
    img.putpixel((local_x + 10, local_y + 10), (255, 0, 0, 255))
    payload = io.BytesIO()
    img.save(payload, format="PNG")
    tile_url = f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png"
    session = FakeSession({tile_url: FakeResponse(200, bytes_payload=payload.getvalue())})

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
    )

    assert frame_result is not None
    assert frame_result.selected_core_pixel_count == 1
    assert frame_result.core_count == 2
    assert len(frame_result.storm_cores) == 2
    assert frame_result.storm_cores[0]["distance_km"] <= frame_result.storm_cores[1]["distance_km"]
    assert frame_result.storm_cores[0]["bearing_degrees"] >= 0
    assert "centroid_latitude" in frame_result.storm_cores[0]
    assert "centroid_longitude" in frame_result.storm_cores[0]


@pytest.mark.asyncio
async def test_analyze_single_frame_merges_adjacent_cores_across_wrapped_tile_boundary() -> None:
    zoom = 7
    tile_size = 512
    center_px_x = 1.0
    center_px_y = 256.0
    center_lat, center_lon = global_px_to_latlon(center_px_x, center_px_y, zoom)
    center_tx = int(center_px_x // tile_size)
    center_ty = int(center_px_y // tile_size)
    assert center_tx == 0

    lookup = {(255, 0, 0, 255): 60}
    left_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    left_tile.putpixel((511, 256), (255, 0, 0, 255))
    left_buf = io.BytesIO()
    left_tile.save(left_buf, format="PNG")

    center_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    center_tile.putpixel((0, 256), (255, 0, 0, 255))
    center_buf = io.BytesIO()
    center_tile.save(center_buf, format="PNG")

    host = "https://tilecache.rainviewer.com"
    path = "/wrap"
    session = FakeSession(
        {
            f"{host}{path}/512/{zoom}/{center_tx}/{center_ty}/2/1_1.png": FakeResponse(
                200, bytes_payload=center_buf.getvalue()
            ),
            f"{host}{path}/512/{zoom}/127/{center_ty}/2/1_1.png": FakeResponse(
                200, bytes_payload=left_buf.getvalue()
            ),
        }
    )

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=1,
        zoom=zoom,
        color_lookup=lookup,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.core_count == 1
    assert frame_result.selected_core_pixel_count == 2


@pytest.mark.asyncio
async def test_analyze_single_frame_keeps_analysis_with_partial_tile_failures() -> None:
    zoom = 7
    tile_size = 512
    center_px_x = 1.0
    center_px_y = 260.0
    center_lat, center_lon = global_px_to_latlon(center_px_x, center_px_y, zoom)
    px, _py = latlon_to_global_px(center_lat, center_lon, zoom)
    tx0 = int(px // tile_size)
    ty0 = int(_py // tile_size)
    assert tx0 == 0

    lookup = {(255, 0, 0, 255): 60}
    tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    local_x = int(px % tile_size)
    local_y = int(_py % tile_size)
    tile.putpixel((local_x, local_y), (255, 0, 0, 255))
    tile_buf = io.BytesIO()
    tile.save(tile_buf, format="PNG")

    host = "https://tilecache.rainviewer.com"
    path = "/partial"
    session = FakeSession(
        {
            f"{host}{path}/512/{zoom}/127/{ty0}/2/1_1.png": FakeResponse(500),
            f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=tile_buf.getvalue()
            ),
        }
    )

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.selected_core_threshold_dbz == 60
    assert frame_result.selected_core_pixel_count == 1
    assert frame_result.complete is False


@pytest.mark.asyncio
@pytest.mark.parametrize(("dbz", "expected_threshold"), ((53, 50), (48, 45)))
async def test_analyze_recent_frames_selects_watch_core_location(
    dbz: int, expected_threshold: int
) -> None:
    """Connected watch and near-watch cores should expose truthful map metadata."""

    center_lat, center_lon = global_px_to_latlon(11000.4, 11000.4, 7)
    px, py = latlon_to_global_px(center_lat, center_lon, 7)
    tx0 = int(px // 512)
    ty0 = int(py // 512)
    local_x = int(px) % 512
    local_y = int(py) % 512

    host = "https://tilecache.rainviewer.com"
    path = "/watch"
    lookup = {(255, 128, 0, 255): dbz}
    tile = _mk_radar_tile(512, lookup, (local_x, local_y), dbz)
    session = FakeSession(
        {
            f"{host}{path}/512/7/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=tile
            )
        }
    )

    result = await analyze_recent_frames(
        session,
        {
            "generated": 1250,
            "host": host,
            "radar": {"past": [{"time": 1200, "path": path}]},
        },
        center_latitude=center_lat,
        center_longitude=center_lon,
        analysis_radius_km=20,
        required_frames=1,
        zoom=7,
        color_lookup=lookup,
        now=1300,
    )

    assert result is not None
    assert result.max_dbz == dbz
    assert result.selected_core_threshold_dbz == expected_threshold
    assert result.selected_core_distance_km is not None
    assert result.selected_core_latitude is not None
    assert result.selected_core_longitude is not None
    assert result.frame_host == host
    assert result.frame_path == path
    assert result.metadata_generated_time == 1250
    assert result.tile_size == 512
    assert result.display_zoom == 7
    assert result.max_native_zoom == 7
    assert result.color_scheme_id == 2
    assert result.tile_options == "1_1"
    assert result.selected_core_centroid_latitude is not None
    assert result.selected_core_centroid_longitude is not None


@pytest.mark.asyncio
async def test_analyze_single_frame_aggregates_across_tiles_not_largest_tile_only() -> None:
    """A broad weak-rain tile must not hide a small stronger core in a neighbor tile."""

    zoom = 7
    tile_size = 512
    tx0 = 20
    ty0 = 20
    center_lat, center_lon = global_px_to_latlon(
        tx0 * tile_size + 510.0,
        ty0 * tile_size + 256.0,
        zoom,
    )
    px, py = latlon_to_global_px(center_lat, center_lon, zoom)
    assert int(px // tile_size) == tx0
    assert int(py // tile_size) == ty0

    lookup = {(1, 1, 1, 255): 5, (255, 0, 0, 255): 60}
    weak_tile = Image.new("RGBA", (tile_size, tile_size), (1, 1, 1, 255))
    weak_buf = io.BytesIO()
    weak_tile.save(weak_buf, format="PNG")

    core_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    core_tile.putpixel((2, 256), (255, 0, 0, 255))
    core_buf = io.BytesIO()
    core_tile.save(core_buf, format="PNG")

    host = "https://tilecache.rainviewer.com"
    path = "/path"
    session = FakeSession(
        {
            f"{host}{path}/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=weak_buf.getvalue()
            ),
            f"{host}{path}/512/{zoom}/{tx0 + 1}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=core_buf.getvalue()
            ),
        }
    )

    frame_result = await analyze_single_radar_frame(
        session,
        host,
        {"time": 123, "path": path},
        center_lat,
        center_lon,
        analysis_radius_km=20,
        zoom=zoom,
        color_lookup=lookup,
    )

    assert isinstance(frame_result, AnalyzedFrame)
    assert frame_result.max_dbz == 60
    assert frame_result.core60_distance_km is not None
    assert frame_result.core60_distance_km <= 20


@pytest.mark.asyncio
async def test_analyze_recent_frames_uses_latest_frame_max_for_current_risk() -> None:
    """Older hail cores must not keep the live dashboard in WARNING after they moved away."""

    zoom = 7
    tile_size = 512
    tx0 = 30
    ty0 = 30
    center_lat, center_lon = global_px_to_latlon(
        tx0 * tile_size + 256.0,
        ty0 * tile_size + 256.0,
        zoom,
    )

    lookup = {(1, 1, 1, 255): 40, (255, 0, 0, 255): 57}
    latest_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    latest_tile.putpixel((256, 256), (1, 1, 1, 255))
    latest_buf = io.BytesIO()
    latest_tile.save(latest_buf, format="PNG")

    older_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    older_tile.putpixel((256, 256), (255, 0, 0, 255))
    older_buf = io.BytesIO()
    older_tile.save(older_buf, format="PNG")

    host = "https://tilecache.rainviewer.com"
    metadata = {
        "host": host,
        "radar": {
            "past": [
                {"time": 2000, "path": "/latest"},
                {"time": 1900, "path": "/older"},
            ]
        },
    }
    session = FakeSession(
        {
            f"{host}/latest/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=latest_buf.getvalue()
            ),
            f"{host}/older/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=older_buf.getvalue()
            ),
        }
    )

    result = await analyze_recent_frames(
        session,
        metadata,
        center_latitude=center_lat,
        center_longitude=center_lon,
        analysis_radius_km=1,
        required_frames=2,
        zoom=zoom,
        color_lookup=lookup,
        now=2100,
    )

    assert result is not None
    assert result.max_dbz == 40
    assert result.selected_core_distance_km is None


@pytest.mark.asyncio
async def test_analyze_recent_frames_estimates_approaching_motion_and_trends() -> None:
    zoom = 7
    tile_size = 512
    tx0 = 31
    ty0 = 31
    center_lat, center_lon = global_px_to_latlon(
        tx0 * tile_size + 256.0,
        ty0 * tile_size + 256.0,
        zoom,
    )

    lookup = {(255, 0, 0, 255): 60, (255, 128, 0, 255): 55}
    latest_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    latest_tile.putpixel((258, 256), (255, 0, 0, 255))
    latest_buf = io.BytesIO()
    latest_tile.save(latest_buf, format="PNG")

    older_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    older_tile.putpixel((278, 256), (255, 128, 0, 255))
    older_buf = io.BytesIO()
    older_tile.save(older_buf, format="PNG")

    host = "https://tilecache.rainviewer.com"
    metadata = {
        "host": host,
        "radar": {
            "past": [
                {"time": 2000, "path": "/latest-motion"},
                {"time": 1400, "path": "/older-motion"},
            ]
        },
    }
    session = FakeSession(
        {
            f"{host}/latest-motion/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=latest_buf.getvalue()
            ),
            f"{host}/older-motion/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=older_buf.getvalue()
            ),
        }
    )

    result = await analyze_recent_frames(
        session,
        metadata,
        center_latitude=center_lat,
        center_longitude=center_lon,
        analysis_radius_km=50,
        required_frames=2,
        zoom=zoom,
        color_lookup=lookup,
        now=2100,
    )

    assert result is not None
    assert result.storm_motion_bearing is not None
    assert result.storm_motion_speed_kmh is not None
    assert result.storm_motion_speed_kmh > 0
    assert result.storm_approaching is True
    assert result.storm_eta_minutes is not None
    assert result.dbz_trend == "rising"
    assert result.distance_trend == "approaching"


@pytest.mark.asyncio
async def test_analyze_recent_frames_estimates_receding_motion() -> None:
    zoom = 7
    tile_size = 512
    tx0 = 32
    ty0 = 32
    center_lat, center_lon = global_px_to_latlon(
        tx0 * tile_size + 256.0,
        ty0 * tile_size + 256.0,
        zoom,
    )

    lookup = {(255, 0, 0, 255): 60}
    latest_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    latest_tile.putpixel((278, 256), (255, 0, 0, 255))
    latest_buf = io.BytesIO()
    latest_tile.save(latest_buf, format="PNG")

    older_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    older_tile.putpixel((258, 256), (255, 0, 0, 255))
    older_buf = io.BytesIO()
    older_tile.save(older_buf, format="PNG")

    host = "https://tilecache.rainviewer.com"
    metadata = {
        "host": host,
        "radar": {
            "past": [
                {"time": 2000, "path": "/latest-recede"},
                {"time": 1400, "path": "/older-recede"},
            ]
        },
    }
    session = FakeSession(
        {
            f"{host}/latest-recede/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=latest_buf.getvalue()
            ),
            f"{host}/older-recede/512/{zoom}/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=older_buf.getvalue()
            ),
        }
    )

    result = await analyze_recent_frames(
        session,
        metadata,
        center_latitude=center_lat,
        center_longitude=center_lon,
        analysis_radius_km=50,
        required_frames=2,
        zoom=zoom,
        color_lookup=lookup,
        now=2100,
    )

    assert result is not None
    assert result.storm_approaching is False
    assert result.storm_eta_minutes is None
    assert result.distance_trend == "receding"


@pytest.mark.asyncio
async def test_analyze_recent_frames_returns_none_for_missing_coverage() -> None:
    center_lat, center_lon = global_px_to_latlon(12345.1, 54321.1, 7)
    center_px = latlon_to_global_px(center_lat, center_lon, 7)
    tx0 = int(center_px[0] // 512)
    ty0 = int(center_px[1] // 512)

    metadata = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [
                {"time": 1000, "path": "/empty"},
            ]
        },
    }

    tile = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    out = io.BytesIO()
    tile.save(out, format="PNG")
    session = FakeSession(
        {
            f"https://tilecache.rainviewer.com/empty/512/7/{tx0}/{ty0}/2/1_1.png": FakeResponse(
                200, bytes_payload=out.getvalue()
            )
        }
    )

    result = await analyze_recent_frames(
        session,
        metadata,
        center_latitude=center_lat,
        center_longitude=center_lon,
        analysis_radius_km=1,
        required_frames=1,
        zoom=7,
        color_lookup={(255, 0, 0, 255): 55},
        now=1_700_000_000,
    )

    assert result is None
