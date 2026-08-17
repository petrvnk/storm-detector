"""Behavior tests for the adaptive Storm Detector Lovelace card."""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/storm_detector/frontend/storm-detector-card.js"


def test_frontend_registers_only_storm_detector_card() -> None:
    source = CARD.read_text(encoding="utf-8")

    assert "customElements.define('storm-detector-card'" in source
    assert "type: 'storm-detector-card'" in source


def _render(
    states: dict[str, dict[str, object]],
    *,
    config: dict[str, object] | None = None,
    trigger_tile_error: bool = False,
    language: str = "cs",
) -> str:
    source = CARD.read_text(encoding="utf-8").replace(
        "customElements.define('storm-detector-card', RadarHailRiskCard);",
        "globalThis.TestCard = RadarHailRiskCard;\n"
        "customElements.define('storm-detector-card', RadarHailRiskCard);",
    )
    script = f"""
let triggerTileError = {json.dumps(trigger_tile_error)};
globalThis.HTMLElement = class {{
  attachShadow() {{
    this.shadowRoot = {{
      innerHTML: '',
      querySelectorAll(selector) {{
        if (selector !== '.radar-tile' || !this.innerHTML.includes('class="radar-tile"')) return [];
        return [{{
          addEventListener(event, callback) {{
            if (event === 'error' && triggerTileError) {{
              triggerTileError = false;
              callback();
            }}
          }},
        }}];
      }},
    }};
    return this.shadowRoot;
  }}
}};
globalThis.customElements = {{ define() {{}} }};
globalThis.window = {{ customCards: [] }};
{source}
const card = new globalThis.TestCard();
card.setConfig({json.dumps(config or {})});
card.hass = {{ language: {json.dumps(language)}, states: {json.dumps(states)} }};
process.stdout.write(card.shadowRoot.innerHTML);
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _render_sequence(
    states: list[dict[str, dict[str, object]]],
    *,
    config: dict[str, object] | None = None,
    trigger_tile_error: bool = False,
    language: str = "cs",
) -> list[str]:
    source = CARD.read_text(encoding="utf-8").replace(
        "customElements.define('storm-detector-card', RadarHailRiskCard);",
        "globalThis.TestCard = RadarHailRiskCard;\n"
        "customElements.define('storm-detector-card', RadarHailRiskCard);",
    )
    script = f"""
let triggerTileError = {json.dumps(trigger_tile_error)};
globalThis.HTMLElement = class {{
  attachShadow() {{
    this.shadowRoot = {{
      innerHTML: '',
      querySelectorAll(selector) {{
        if (selector !== '.radar-tile' || !this.innerHTML.includes('class="radar-tile"')) return [];
        return [{{
          addEventListener(event, callback) {{
            if (event === 'error' && triggerTileError) {{
              triggerTileError = false;
              callback();
            }}
          }},
        }}];
      }},
    }};
    return this.shadowRoot;
  }}
}};
globalThis.customElements = {{ define() {{}} }};
globalThis.window = {{ customCards: [] }};
{source}
const card = new globalThis.TestCard();
card.setConfig({json.dumps(config or {})});
const rendered = [];
for (const states of {json.dumps(states)}) {{
  card.hass = {{ language: {json.dumps(language)}, states }};
  rendered.push(card.shadowRoot.innerHTML);
}}
process.stdout.write(JSON.stringify(rendered));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _states(
    level: str,
    *,
    evidence_kind: str,
    stale: bool = False,
    attributes: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    attrs: dict[str, object] = {
        "evidence_kind": evidence_kind,
        "is_stale": stale,
        "source_status": {"radar": "ok", "lightning": "not_configured"},
    }
    attrs.update(attributes or {})
    overlay = attrs.get("radar_overlay")
    if isinstance(overlay, dict):
        frame = overlay.get("frame")
        if isinstance(frame, dict):
            attrs.setdefault("frame_age_seconds", frame.get("age_seconds"))
        cores = overlay.get("cores")
        if isinstance(cores, list):
            selected = next(
                (core for core in cores if isinstance(core, dict) and core.get("selected") is True),
                None,
            )
            if selected is not None:
                attrs.setdefault("selected_core_distance_km", selected.get("distance_km"))
                attrs.setdefault("selected_core_threshold_dbz", selected.get("threshold_dbz"))
                attrs.setdefault("selected_core_max_dbz", selected.get("max_dbz"))
    return {
        "sensor.storm_detector_level": {"state": level, "attributes": attrs},
        "sensor.storm_detector_summary": {"state": "Internal summary", "attributes": {}},
        "binary_sensor.storm_detector_active": {
            "state": "off" if level in {"none", "unavailable"} else "on",
            "attributes": {},
        },
        "binary_sensor.storm_detector_data_stale": {
            "state": "on" if stale else "off",
            "attributes": {},
        },
    }


def _radar_overlay(
    *,
    frame_time: int = 1_710_000_000,
    radius_km: float = 80.0,
    tile_url_template: str = (
        "https://tilecache.rainviewer.com/v2/radar/1710000000/"
        "512/{z}/{x}/{y}/2/1_1.png"
    ),
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ok",
        "provider": "RainViewer",
        "mode": "rainviewer_tile_mosaic",
        "attribution": {
            "label": "Weather data by RainViewer",
            "url": "https://www.rainviewer.com/",
        },
        "frame": {
            "time": frame_time,
            "time_iso": "2024-03-09T16:00:00Z",
            "age_seconds": 120,
            "tile_url_template": tile_url_template,
            "tile_size": 512,
            "display_zoom": 7,
            "max_native_zoom": 7,
        },
        "viewport": {
            "center_latitude": 50.0755,
            "center_longitude": 14.4378,
            "radius_km": radius_km,
            "warning_radius_km": 25,
            "urgent_radius_km": 15,
        },
        "selected_core_id": f"{frame_time}:core:2",
        "cores": [
            {
                "id": f"{frame_time}:core:1",
                "frame_time": frame_time,
                "selected": False,
                "role": "context",
                "threshold_dbz": 50,
                "max_dbz": 52,
                "distance_km": 8.0,
                "render_latitude": 50.11,
                "render_longitude": 14.35,
            },
            {
                "id": f"{frame_time}:core:2",
                "frame_time": frame_time,
                "selected": True,
                "role": "risk_driver",
                "threshold_dbz": 55,
                "max_dbz": 57,
                "distance_km": 25.0,
                "centroid_latitude": 49.99,
                "centroid_longitude": 14.48,
            },
        ],
        "limits": {
            "core_count_total": 2,
            "core_count_rendered": 2,
            "core_limit": 12,
            "selected_core_forced_included": False,
        },
    }


# Batch 1 contract assumptions used by these frontend regression tests:
# - frame_time and frame_age_seconds must match between sensor attrs and radar_overlay.frame
# - one selected core is explicitly identified by selected_core_id and mirrors selected_* attrs
# - selected core position is expected from render_{latitude,longitude} when available
EARTH_CIRCUMFERENCE_M = 2 * math.pi * 6378137


def _web_mercator_xy(
    latitude: float,
    longitude: float,
    *,
    zoom: float,
    tile_size: float,
) -> tuple[float, float]:
    bounded_latitude = min(85.05112878, max(-85.05112878, latitude))
    world_size = (2**zoom) * tile_size
    latitude_radians = math.radians(bounded_latitude)
    return (
        ((longitude + 180) / 360) * world_size,
        ((1 - math.asinh(math.tan(latitude_radians)) / math.pi) / 2) * world_size,
    )


def _live_grid(overlay: dict[str, object]) -> dict[str, float]:
    frame = overlay["frame"]
    viewport = overlay["viewport"]
    assert isinstance(frame, dict)
    assert isinstance(viewport, dict)

    zoom = float(frame["display_zoom"])
    tile_size = int(frame["tile_size"])
    center_x, center_y = _web_mercator_xy(
        float(viewport["center_latitude"]),
        float(viewport["center_longitude"]),
        zoom=zoom,
        tile_size=tile_size,
    )
    meters_per_pixel = (
        math.cos(float(viewport["center_latitude"]) * math.pi / 180)
        * EARTH_CIRCUMFERENCE_M
    ) / ((2**zoom) * tile_size)
    radius_pixels = float(viewport["radius_km"]) * 1000 / meters_per_pixel
    min_x = math.floor((center_x - radius_pixels) / tile_size)
    max_x = math.floor((center_x + radius_pixels) / tile_size)
    world_tiles = 2**zoom
    min_y = max(0, math.floor((center_y - radius_pixels) / tile_size))
    max_y = min(world_tiles - 1, math.floor((center_y + radius_pixels) / tile_size))
    return {
        "zoom": int(zoom),
        "tile_size": tile_size,
        "min_x": min_x,
        "max_x": max_x,
        "min_y": min_y,
        "max_y": max_y,
        "world_tiles": int(world_tiles),
        "width": radius_pixels * 2,
        "height": radius_pixels * 2,
        "center_x": center_x,
        "center_y": center_y,
        "origin_x": center_x - radius_pixels,
        "origin_y": center_y - radius_pixels,
    }


def _expected_selected_marker_xy(overlay: dict[str, object], latitude: float, longitude: float) -> tuple[float, float]:
    grid = _live_grid(overlay)
    point_x, point_y = _web_mercator_xy(
        latitude=latitude,
        longitude=longitude,
        zoom=float(grid["zoom"]),
        tile_size=grid["tile_size"],
    )
    world_size = grid["world_tiles"] * grid["tile_size"]
    if point_x - grid["center_x"] > world_size / 2:
        point_x -= world_size
    if point_x - grid["center_x"] < -world_size / 2:
        point_x += world_size
    return point_x - grid["origin_x"], point_y - grid["origin_y"]


def _selected_live_core_xy(html: str, core_id: str) -> tuple[float, float]:
    match = re.search(
        rf'class="live-core selected" data-core-id="{re.escape(core_id)}" '
        r'data-projected-x="([^"]+)" data-projected-y="([^"]+)"',
        html,
    )
    assert match is not None
    return float(match.group(1)), float(match.group(2))


def test_clear_state_is_compact_and_hides_diagnostics() -> None:
    html = _render(_states("none", evidence_kind="none"))

    assert "Silné radarové jádro v okolí nezjištěno" in html
    assert "Max dBZ" not in html
    assert "Confidence" not in html
    assert "<svg" not in html


def test_lightning_only_warning_never_claims_hail() -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="lightning_only",
            attributes={
                "lightning_distance_km": 14.2,
                "source_status": {"radar": "ok", "lightning": "ok"},
            },
        )
    )

    assert "Blesky poblíž" in html
    assert html.count('class="hail-note"') == 1
    assert html.count("Kroupy nejsou radarově potvrzené") == 1
    assert 'class="safety-note"' not in html
    assert "Radarová aktivita není potvrzené krupobití" not in html
    assert "sledujte oficiální výstrahy" not in html
    assert "Možné kroupy" not in html
    assert "14.2 km" in html


def test_hail_wording_requires_radar_hail_evidence() -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "selected_core_distance_km": 12.4,
                "storm_approaching": True,
                "storm_eta_minutes": 23,
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert "Možné kroupy" in html
    assert "12.4 km" in html
    assert "Přibližuje se" in html
    assert "přibližně 20–25 min" in html


def test_high_hail_state_requires_urgent_radar_hail_evidence() -> None:
    html = _render(
        _states(
            "urgent",
            evidence_kind="radar_hail",
            attributes={
                "selected_core_distance_km": 6.1,
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert "Vysoká možnost krup" in html
    assert "6.1 km" in html


def test_stale_state_hides_previous_event_values() -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            stale=True,
            attributes={
                "selected_core_distance_km": 3.2,
                "storm_approaching": True,
                "storm_eta_minutes": 5,
            },
        )
    )

    assert "Detekce dočasně není dostupná" in html
    assert "Možné kroupy" not in html
    assert "3.2 km" not in html
    assert "ETA" not in html


def test_unreliable_or_stale_optional_values_are_omitted() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 31.0,
                "storm_approaching": None,
                "storm_eta_minutes": 18,
                "lightning_distance_km": 7.0,
                "source_status": {"radar": "ok", "lightning": "stale"},
            },
        )
    )

    assert "Bouřka v okolí" in html
    assert "31.0 km" in html
    assert "ETA" not in html
    assert "7.0 km" not in html
    assert "Confidence" not in html


def test_radar_storm_shows_core_intensity_and_area() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 63.4,
                "selected_core_max_dbz": 56,
                "selected_core_area_km2": 18.7,
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html
    assert "63.4 km" in html
    assert "Intenzita jádra" in html
    assert "56 dBZ" in html
    assert "Plocha jádra" in html
    assert "18.7 km²" in html


def test_schematic_uses_core_bearing_not_motion_bearing() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 40.0,
                "storm_motion_bearing": 0.0,
                "storm_cores": [{"distance_km": 40.0, "bearing_degrees": 180.0}],
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    match = re.search(r'class="core-node selected" cx="([^"]+)" cy="([^"]+)"', html)
    assert match is not None
    x, y = (float(value) for value in match.groups())
    assert abs(x - 90) < 1
    assert y > 130


def test_schematic_renders_all_detected_cores_and_highlights_selected() -> None:
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "selected_core_distance_km": 25.0,
                "selected_core_max_dbz": 55,
                "storm_cores": [
                    {"distance_km": 25.0, "bearing_degrees": 180.0, "max_dbz": 55},
                    {"distance_km": 42.0, "bearing_degrees": 240.0, "max_dbz": 49},
                    {"distance_km": 68.0, "bearing_degrees": 300.0, "max_dbz": 46},
                ],
                "source_status": {"radar": "ok", "lightning": "not_configured"},
            },
        )
    )

    assert html.count('class="core-node secondary"') == 2
    assert html.count('class="core-node selected"') == 1
    assert "Detekovaná jádra" in html
    assert ">3</strong>" in html
    assert "hlavní jádro od domova" in html
    assert "Radarová aktivita není potvrzené krupobití" in html
    assert html.count("sledujte oficiální výstrahy") == 1


def test_valid_overlay_renders_backend_tiles_and_backend_selected_core() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        )
    )

    assert 'class="radar-live"' in html
    assert 'role="img"' in html
    assert 'aria-label="Radarový snímek RainViewer' in html
    assert 'class="radar-tiles"' in html
    assert 'class="live-ring monitoring"' in html
    assert 'class="live-home"' in html
    assert 1 <= html.count('class="radar-tile"') <= 9
    assert "/512/7/" in html
    assert 'loading="lazy"' in html
    assert 'decoding="async"' in html
    assert 'referrerpolicy="no-referrer"' in html
    assert 'alt=""' in html
    assert 'aria-hidden="true"' in html
    assert html.count('class="live-core secondary"') == 1
    assert html.count('class="live-core selected"') == 1
    assert f'data-core-id="{frame_time}:core:2"' in html
    assert (
        '<a href="https://www.rainviewer.com/" target="_blank" '
        'rel="noopener noreferrer">Data o počasí od RainViewer</a>'
    ) in html
    assert html.count("Radarová aktivita není potvrzené krupobití") == 1
    assert html.count("sledujte oficiální výstrahy") == 1


def test_live_overlay_count_uses_published_limits_and_discloses_cap() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    cores = overlay["cores"]
    limits = overlay["limits"]
    assert isinstance(cores, list)
    assert isinstance(limits, dict)
    cores.extend(
        {
            "id": f"{frame_time}:core:{index}",
            "frame_time": frame_time,
            "selected": False,
            "role": "context",
            "threshold_dbz": 50,
            "max_dbz": 51,
            "distance_km": 30.0 + index,
            "render_latitude": 50.0 + index / 1000,
            "render_longitude": 14.4 + index / 1000,
        }
        for index in range(3, 13)
    )
    limits.update(core_count_total=13, core_count_rendered=12)
    legacy_cores = [
        {"distance_km": float(index + 1), "bearing_degrees": float(index * 30)}
        for index in range(8)
    ]

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "storm_cores": legacy_cores,
                "radar_overlay": overlay,
            },
        )
    )

    assert html.count('class="live-core secondary"') == 11
    assert html.count('class="live-core selected"') == 1
    assert "Zobrazeno" in html
    assert "12 z 13 jader" in html
    assert "Detekovaná jádra" not in html
    assert ">8</strong>" not in html


def test_live_overlay_stacks_backend_selected_core_above_secondary_cores() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    cores = overlay["cores"]
    assert isinstance(cores, list)
    cores.reverse()

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={"frame_time": frame_time, "radar_overlay": overlay},
        )
    )

    assert html.rfind('class="live-core secondary"') < html.index(
        'class="live-core selected"'
    )


def test_live_overlay_home_label_tracks_projected_home_marker() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        )
    )

    marker = re.search(
        r'class="live-home" style="left:([^%]+)%;top:([^%]+)%"', html
    )
    label = re.search(
        r'class="live-home-label" style="left:([^%]+)%;top:([^%]+)%"', html
    )
    assert marker is not None and label is not None
    marker_x, marker_y = (float(value) for value in marker.groups())
    label_x, label_y = (float(value) for value in label.groups())
    assert label_x == pytest.approx(marker_x)
    assert label_y == pytest.approx(marker_y)


def test_live_overlay_raster_and_svg_share_explicit_pixel_viewport() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        )
    )

    stage = re.search(r'class="radar-live-stage" style="aspect-ratio:([^/]+)/([^"]+)"', html)
    overlay = re.search(
        r'class="radar-live-overlay" viewBox="0 0 ([^ ]+) ([^"]+)" preserveAspectRatio="none"',
        html,
    )
    assert stage is not None and overlay is not None
    assert tuple(float(value) for value in stage.groups()) == tuple(
        float(value) for value in overlay.groups()
    )
    stage_width, stage_height = (float(value) for value in stage.groups())
    assert stage_width == pytest.approx(stage_height)


def test_live_overlay_home_is_exactly_centered_in_square_viewport() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        )
    )

    marker = re.search(
        r'class="live-home" style="left:([^%]+)%;top:([^%]+)%"', html
    )
    ring = re.search(
        r'class="live-ring monitoring" cx="([^"]+)" cy="([^"]+)" r="([^"]+)"',
        html,
    )
    viewport = re.search(
        r'class="radar-live-overlay" viewBox="0 0 ([^ ]+) ([^"]+)"', html
    )
    assert marker is not None and ring is not None and viewport is not None
    assert tuple(float(value) for value in marker.groups()) == pytest.approx((50.0, 50.0))
    cx, cy, radius = (float(value) for value in ring.groups())
    width, height = (float(value) for value in viewport.groups())
    assert width == pytest.approx(height)
    assert cx == pytest.approx(width / 2)
    assert cy == pytest.approx(height / 2)
    assert radius == pytest.approx(width / 2)


def test_live_overlay_keeps_north_up_and_east_right() -> None:
    frame_time = 1_710_000_000

    def rendered_selected_xy(latitude: float, longitude: float) -> tuple[float, float]:
        overlay = _radar_overlay(frame_time=frame_time)
        viewport = overlay["viewport"]
        cores = overlay["cores"]
        assert isinstance(viewport, dict) and isinstance(cores, list)
        selected = next(core for core in cores if core["selected"] is True)
        selected["render_latitude"] = latitude
        selected["render_longitude"] = longitude
        html = _render(
            _states(
                "warning",
                evidence_kind="radar_hail",
                attributes={
                    "frame_time": frame_time,
                    "selected_core_distance_km": 25.0,
                    "radar_overlay": overlay,
                },
            )
        )
        return _selected_live_core_xy(html, str(overlay["selected_core_id"]))

    north_x, north_y = rendered_selected_xy(50.1755, 14.4378)
    east_x, east_y = rendered_selected_xy(50.0755, 14.5378)
    grid = _live_grid(_radar_overlay(frame_time=frame_time))
    center_x = grid["width"] / 2
    center_y = grid["height"] / 2

    assert north_x == pytest.approx(center_x, abs=0.2)
    assert north_y < center_y
    assert east_x > center_x
    assert east_y == pytest.approx(center_y, abs=0.2)


def test_live_markers_use_fixed_screen_space_geometry_at_320_px() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        )
    )
    source = CARD.read_text(encoding="utf-8")

    assert '<div class="radar-markers" aria-hidden="true">' in html
    assert html.index("</svg>") < html.index('<div class="radar-markers"')
    positions = re.findall(
        r'class="live-(?:home|core (?:secondary|selected))"[^>]*'
        r'style="left:([^%]+)%;top:([^%]+)%"',
        html,
    )
    assert len(positions) == 3
    for left, top in positions:
        screen_x = float(left) / 100 * 320
        screen_y = float(top) / 100 * 320
        assert 0 <= screen_x <= 320
        assert 0 <= screen_y <= 320

    size_rules = {}
    for selector in (
        "live-home",
        "live-core secondary",
        "live-core selected",
        "live-core-halo",
    ):
        css_selector = selector.replace(" ", r"\.")
        match = re.search(
            rf"\.{css_selector} \{{[^}}]*width:(\d+)px; height:(\d+)px;",
            source,
        )
        assert match is not None
        size_rules[selector] = tuple(int(value) for value in match.groups())
    assert size_rules["live-home"][0] >= 10
    assert size_rules["live-core secondary"][0] >= 9
    assert size_rules["live-core selected"][0] > size_rules["live-core secondary"][0]
    assert 18 <= size_rules["live-core-halo"][0] <= 24
    assert all(width == height for width, height in size_rules.values())


def test_tile_load_error_falls_back_to_schematic_with_notice() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        ),
        trigger_tile_error=True,
    )

    assert 'class="radar-tile"' not in html
    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html
    assert "Radarová vrstva se nepodařila načíst" in html
    assert "Bouřka v okolí" in html


def test_tile_load_error_is_scoped_to_the_failed_frame() -> None:
    failed_time = 1_710_000_000
    next_time = failed_time + 600
    rendered = _render_sequence(
        [
            _states(
                "watch",
                evidence_kind="radar_storm",
                attributes={
                    "frame_time": failed_time,
                    "storm_cores": [
                        {"distance_km": 25.0, "bearing_degrees": 180.0}
                    ],
                    "radar_overlay": _radar_overlay(frame_time=failed_time),
                },
            ),
            _states(
                "watch",
                evidence_kind="radar_storm",
                attributes={
                    "frame_time": next_time,
                    "storm_cores": [
                        {"distance_km": 25.0, "bearing_degrees": 180.0}
                    ],
                    "radar_overlay": _radar_overlay(frame_time=next_time),
                },
            ),
        ],
        trigger_tile_error=True,
    )

    assert 'class="radar-tile"' not in rendered[0]
    assert "Radarová vrstva se nepodařila načíst" in rendered[0]
    assert 'class="radar-live"' in rendered[1]
    assert 'class="radar-tile"' in rendered[1]
    assert "Radarová vrstva se nepodařila načíst" not in rendered[1]


def test_live_overlay_css_is_mobile_safe_and_respects_reduced_motion() -> None:
    source = CARD.read_text(encoding="utf-8")

    assert ":host { display:block; max-width:100%; overflow-x:hidden; }" in source
    assert ".radar-live-stage {" in source
    assert "width:min(100%, 420px)" in source
    assert "margin-inline:auto" in source
    assert "min-height:220px" not in source
    assert "max-height:320px" not in source
    assert "@media (max-width:600px)" in source
    assert ".radar-live-stage { width:100%; }" in source
    assert ".facts { grid-template-columns:1fr; }" in source
    assert ".radar-live-meta { flex-direction:column" in source
    assert "@media (prefers-reduced-motion: reduce)" in source
    assert ".live-core-halo { animation:none; }" in source


def test_overlay_config_auto_off_and_always_gating() -> None:
    frame_time = 1_710_000_000
    empty_overlay = _radar_overlay(frame_time=frame_time)
    empty_overlay["selected_core_id"] = None
    empty_overlay["cores"] = []
    empty_overlay["limits"] = {
        "core_count_total": 0,
        "core_count_rendered": 0,
        "core_limit": 12,
        "selected_core_forced_included": False,
    }
    clear_states = _states(
        "none",
        evidence_kind="none",
        attributes={"frame_time": frame_time, "radar_overlay": empty_overlay},
    )

    auto_html = _render(clear_states)
    always_html = _render(clear_states, config={"radar_overlay": "always"})
    off_html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        ),
        config={"radar_overlay": "off"},
    )

    assert 'class="risk-card compact clear"' in auto_html
    assert 'class="radar-tile"' not in auto_html
    assert 'class="radar-live"' in always_html
    assert "Silné radarové jádro v okolí nezjištěno" in always_html
    assert 'class="radar-tile"' not in off_html
    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in off_html


def test_overlay_fallback_keeps_hail_mode_status_and_facts() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    overlay["status"] = "stale"

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.3,
                "selected_core_max_dbz": 58,
                "selected_core_area_km2": 12.5,
                "storm_approaching": True,
                "storm_eta_minutes": 9,
                "storm_cores": [{"distance_km": 25.3, "bearing_degrees": 180.0}],
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="risk-card hail-possible"' in html
    assert 'Možné kroupy' in html
    assert 'Radar ukazuje silné jádro s možností krup.' in html
    assert 'Nejbližší jádro' in html
    assert '25.3 km' in html
    assert 'Intenzita jádra' in html
    assert '58 dBZ' in html
    assert 'Příchod' in html
    assert 'Přibližuje se' in html
    assert 'class="radar-live"' not in html
    assert 'aria-label="Radarový snímek RainViewer' not in html


def test_frame_or_selected_core_mismatch_falls_back_to_schematic() -> None:
    frame_time = 1_710_000_000
    frame_mismatch = _radar_overlay(frame_time=frame_time + 600)
    selected_mismatch = _radar_overlay(frame_time=frame_time)
    selected_mismatch["selected_core_id"] = "missing-core"
    common = {
        "frame_time": frame_time,
        "selected_core_distance_km": 25.0,
        "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
    }

    for overlay in (frame_mismatch, selected_mismatch):
        html = _render(
            _states(
                "watch",
                evidence_kind="radar_storm",
                attributes={**common, "radar_overlay": overlay},
            )
        )
        assert 'class="radar-tile"' not in html
        assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_missing_frame_time_fails_closed_to_schematic() -> None:
    overlay = _radar_overlay()
    frame = overlay["frame"]
    cores = overlay["cores"]
    assert isinstance(frame, dict)
    assert isinstance(cores, list)
    frame["time"] = None
    for core in cores:
        core["frame_time"] = None

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": None,
                "selected_core_distance_km": 25.0,
                "storm_cores": [
                    {"distance_km": 25.0, "bearing_degrees": 180.0}
                ],
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-live"' not in html
    assert 'class="radar-tile"' not in html
    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_empty_selected_core_id_fails_closed_to_schematic() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    cores = overlay["cores"]
    assert isinstance(cores, list)
    selected = next(core for core in cores if core["selected"] is True)
    overlay["selected_core_id"] = ""
    selected["id"] = ""

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "storm_cores": [
                    {"distance_km": 25.0, "bearing_degrees": 180.0}
                ],
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-live"' not in html
    assert 'class="radar-tile"' not in html
    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_frame_age_and_selected_core_values_must_stay_synchronized() -> None:
    frame_time = 1_710_000_000
    mismatches = (
        {"frame_age_seconds": 999},
        {"selected_core_distance_km": 99.0},
        {"selected_core_threshold_dbz": 50},
        {"selected_core_max_dbz": 40},
    )

    for mismatch in mismatches:
        html = _render(
            _states(
                "watch",
                evidence_kind="radar_storm",
                attributes={
                    "frame_time": frame_time,
                    "storm_cores": [
                        {"distance_km": 25.0, "bearing_degrees": 180.0}
                    ],
                    "radar_overlay": _radar_overlay(frame_time=frame_time),
                    **mismatch,
                },
            )
        )
        assert 'class="radar-tile"' not in html
        assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_selected_core_outside_tile_grid_falls_back_to_schematic() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    cores = overlay["cores"]
    assert isinstance(cores, list)
    selected = next(core for core in cores if core["selected"] is True)
    selected["centroid_latitude"] = 0.0
    selected["centroid_longitude"] = 0.0

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "storm_cores": [
                    {"distance_km": 25.0, "bearing_degrees": 180.0}
                ],
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-tile"' not in html
    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_selected_core_wraps_across_antimeridian_in_live_overlay() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    viewport = overlay["viewport"]
    assert isinstance(viewport, dict)
    viewport["center_latitude"] = 0.0
    viewport["center_longitude"] = 179.8
    cores = overlay["cores"]
    assert isinstance(cores, list)
    selected = next(core for core in cores if core["selected"] is True)
    selected["centroid_latitude"] = 0.0
    selected["centroid_longitude"] = -179.8

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={"frame_time": frame_time, "radar_overlay": overlay},
        )
    )

    assert 'class="radar-live"' in html
    assert html.count('class="live-core selected"') == 1


def test_invalid_tile_templates_and_tile_cap_fail_closed() -> None:
    frame_time = 1_710_000_000
    templates = (
        "http://tilecache.rainviewer.com/frame/{z}/{x}/{y}.png",
        "javascript:alert(1)/{z}/{x}/{y}",
        "data:image/png;base64,{z}/{x}/{y}",
        "https://tilecache.rainviewer.com/frame/{z}/{x}.png",
        "https://tilecache.rainviewer.com/frame/{z}/{x}/{y}/{token}.png",
        "https://tilecache.rainviewer.com/frame/{z}/{x}/{y}.png\nignored",
        "https://tilecache.rainviewer.com/frame/{z}/{x}/{y}.png\u0000ignored",
    )
    overlays = [
        _radar_overlay(frame_time=frame_time, tile_url_template=template)
        for template in templates
    ]
    overlays.append(_radar_overlay(frame_time=frame_time, radius_km=5_000.0))

    for overlay in overlays:
        html = _render(
            _states(
                "watch",
                evidence_kind="radar_storm",
                attributes={
                    "frame_time": frame_time,
                    "selected_core_distance_km": 25.0,
                    "storm_cores": [
                        {"distance_km": 25.0, "bearing_degrees": 180.0}
                    ],
                    "radar_overlay": overlay,
                },
            )
        )
        assert 'class="radar-tile"' not in html
        assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_default_eighty_km_viewport_falls_back_above_nine_tiles() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    viewport = overlay["viewport"]
    assert isinstance(viewport, dict)
    viewport["center_latitude"] = 80.0
    cores = overlay["cores"]
    assert isinstance(cores, list)
    for index, core in enumerate(cores):
        core["render_latitude"] = 80.0 - index * 0.05
        core["render_longitude"] = 14.4378 + index * 0.05

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "storm_cores": [
                    {"distance_km": 25.0, "bearing_degrees": 180.0}
                ],
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-tile"' not in html
    assert 'aria-label="Polohy bouřkových jader vůči domovu"' in html


def test_overlay_zoom_is_clamped_and_all_position_fallbacks_render() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    frame = overlay["frame"]
    assert isinstance(frame, dict)
    frame["display_zoom"] = 9
    frame["max_native_zoom"] = 9
    cores = overlay["cores"]
    assert isinstance(cores, list)
    cores.append(
        {
            "id": f"{frame_time}:core:3",
            "frame_time": frame_time,
            "selected": False,
            "latitude": 50.02,
            "longitude": 14.52,
        }
    )

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "radar_overlay": overlay,
            },
        )
    )

    assert "/512/7/" in html
    assert "/512/9/" not in html
    assert html.count('class="live-core secondary"') == 2
    assert html.count('class="live-core selected"') == 1


@pytest.mark.parametrize(
    "status",
    ("stale", "unavailable", "degraded", "disabled"),
)
def test_non_ok_overlay_status_is_not_rendered_as_live(status: str) -> None:
    # Batch 1 fixture: status must be "ok" for eligible live rendering.
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    overlay["status"] = status

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
                "selected_core_distance_km": 25.0,
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-live"' not in html
    assert 'class="radar-tile"' not in html
    assert 'Weather data by RainViewer' not in html


@pytest.mark.parametrize(
    "source_state",
    ("unavailable", "degraded", "stale", "error"),
)
def test_radar_source_not_ok_forces_overlay_offline_fallback(source_state: str) -> None:
    # Batch 1 source_status gate: overlay is only eligible when source_status.radar == "ok".
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "source_status": {"radar": source_state, "lightning": "not_configured"},
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-live"' not in html
    assert 'class="radar-tile"' not in html


@pytest.mark.parametrize(
    "modify_selected",
    ("selected_false", "id_out_of_sync"),
)
def test_selected_core_id_contract_is_strict(modify_selected: str) -> None:
    # Batch 1 contract: a backend-selected core must be uniquely selected and match selected_core_id.
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)

    if modify_selected == "selected_false":
        selected = next(core for core in overlay["cores"] if core["selected"] is True)
        selected["selected"] = False
    else:
        overlay["selected_core_id"] = "missing-core-id"

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "selected_core_threshold_dbz": 55,
                "selected_core_max_dbz": 57,
                "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-live"' not in html
    assert 'class="radar-tile"' not in html


def test_live_overlay_enforces_hard_tile_cap_25() -> None:
    # Batch 1 acceptance: cap live tile requests at 25 before rendering.
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time, radius_km=8_000.0)

    html = _render(
        _states(
            "watch",
            evidence_kind="radar_storm",
            attributes={
                "frame_time": frame_time,
                "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
                "selected_core_distance_km": 25.0,
                "radar_overlay": overlay,
            },
        )
    )

    assert 'class="radar-live"' not in html
    assert 'class="radar-tile"' not in html


def test_core_position_prefers_render_coordinates_then_centroid_then_latlon() -> None:
    # Batch 1 coordinate contract: render_* -> centroid_* -> fallback lat/lon.
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    viewport = overlay["viewport"]
    assert isinstance(viewport, dict)
    viewport["radius_km"] = 120.0
    viewport["center_latitude"] = 50.0
    viewport["center_longitude"] = 14.0

    cores = overlay["cores"]
    assert isinstance(cores, list)
    selected = next(core for core in cores if core["selected"] is True)

    selected["render_latitude"] = 50.04
    selected["render_longitude"] = 14.06
    selected["centroid_latitude"] = 49.0
    selected["centroid_longitude"] = 30.0
    selected["latitude"] = 48.9
    selected["longitude"] = 12.0

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "selected_core_threshold_dbz": 55,
                "selected_core_max_dbz": 57,
                "radar_overlay": overlay,
            },
        )
    )
    x, y = _selected_live_core_xy(html, str(overlay["selected_core_id"]))
    expected_x, expected_y = _expected_selected_marker_xy(overlay, 50.04, 14.06)
    assert x == pytest.approx(expected_x, abs=0.8)
    assert y == pytest.approx(expected_y, abs=0.8)

    selected.pop("render_latitude", None)
    selected.pop("render_longitude", None)
    selected["centroid_latitude"] = 50.02
    selected["centroid_longitude"] = 14.05

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "selected_core_threshold_dbz": 55,
                "selected_core_max_dbz": 57,
                "radar_overlay": overlay,
            },
        )
    )
    x, y = _selected_live_core_xy(html, str(overlay["selected_core_id"]))
    expected_x, expected_y = _expected_selected_marker_xy(overlay, 50.02, 14.05)
    assert x == pytest.approx(expected_x, abs=0.8)
    assert y == pytest.approx(expected_y, abs=0.8)

    selected.pop("centroid_latitude", None)
    selected.pop("centroid_longitude", None)
    selected["latitude"] = 50.00
    selected["longitude"] = 14.06

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "selected_core_threshold_dbz": 55,
                "selected_core_max_dbz": 57,
                "radar_overlay": overlay,
            },
        )
    )
    x, y = _selected_live_core_xy(html, str(overlay["selected_core_id"]))
    expected_x, expected_y = _expected_selected_marker_xy(overlay, 50.0, 14.06)
    assert x == pytest.approx(expected_x, abs=0.8)
    assert y == pytest.approx(expected_y, abs=0.8)


def test_stale_state_never_renders_overlay_tiles_cores_or_eta() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            stale=True,
            attributes={
                "frame_time": frame_time,
                "selected_core_distance_km": 25.0,
                "storm_approaching": True,
                "storm_eta_minutes": 10,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        )
    )

    assert "Detekce dočasně není dostupná" in html
    assert 'class="radar-tile"' not in html
    assert 'class="live-core' not in html
    assert f"{frame_time}:core:2" not in html
    assert "Příchod" not in html
    assert "10 min" not in html


def test_unavailable_state_refuses_live_overlay_payload() -> None:
    frame_time = 1_710_000_000
    previous, unavailable = _render_sequence(
        [
            _states(
                "warning",
                evidence_kind="radar_storm",
                attributes={
                    "frame_time": frame_time,
                    "selected_core_distance_km": 25.0,
                    "storm_cores": [{"distance_km": 25.0, "bearing_degrees": 180.0}],
                    "radar_overlay": _radar_overlay(frame_time=frame_time),
                },
            ),
            _states(
                "unavailable",
                evidence_kind="none",
                attributes={
                    "frame_time": frame_time,
                    "radar_overlay": _radar_overlay(frame_time=frame_time),
                },
            ),
        ]
    )

    assert 'class="radar-live"' in previous
    assert 'class="radar-tile"' in previous
    assert f"{frame_time}:core:2" in previous

    assert 'class="radar-live"' not in unavailable
    assert 'class="radar-tile"' not in unavailable
    assert 'class="live-core' not in unavailable
    assert f"{frame_time}:core:2" not in unavailable


def test_stale_state_update_clears_previous_live_overlay_dom() -> None:
    frame_time = 1_710_000_000
    old_overlay = _radar_overlay(frame_time=frame_time)
    current, stale = _render_sequence(
        [
            _states(
                "warning",
                evidence_kind="radar_hail",
                attributes={"frame_time": frame_time, "radar_overlay": old_overlay},
            ),
            _states(
                "warning",
                evidence_kind="radar_hail",
                stale=True,
                attributes={"frame_time": frame_time, "radar_overlay": old_overlay},
            ),
        ]
    )

    assert 'class="radar-live"' in current
    assert 'class="radar-tile"' in current
    assert 'class="radar-live"' not in stale
    assert 'class="radar-tile"' not in stale
    assert 'class="live-core' not in stale
    assert f"{frame_time}:core:2" not in stale


def test_live_radar_module_stays_below_dom_node_budget() -> None:
    frame_time = 1_710_000_000
    overlay = _radar_overlay(frame_time=frame_time)
    cores = overlay["cores"]
    limits = overlay["limits"]
    assert isinstance(cores, list)
    assert isinstance(limits, dict)
    cores.extend(
        {
            "id": f"{frame_time}:core:{index}",
            "frame_time": frame_time,
            "selected": False,
            "render_latitude": 50.0 + index / 1000,
            "render_longitude": 14.4 + index / 1000,
        }
        for index in range(3, 13)
    )
    limits.update(core_count_total=12, core_count_rendered=12)

    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={"frame_time": frame_time, "radar_overlay": overlay},
        )
    )
    radar_html = html.split('<section class="radar-live"', 1)[1].split(
        "</section>", 1
    )[0]

    assert len(re.findall(r"<(?:a|div|img|section|span|svg|circle)\b", radar_html)) < 120


def test_frontend_has_no_rainviewer_metadata_fetch_path() -> None:
    source = CARD.read_text(encoding="utf-8")

    assert "weather-maps-api" not in source
    assert "weather-maps.json" not in source
    assert "fetch(" not in source


@pytest.mark.parametrize("language", ["en", "de", ""])
def test_non_czech_languages_use_complete_english_fallback(language: str) -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail_with_lightning",
            attributes={
                "frame_time": frame_time,
                "lightning_distance_km": 9.4,
                "source_status": {"radar": "ok", "lightning": "ok"},
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        ),
        language=language,
    )

    assert "Storm Detector" in html
    assert "Possible hail" in html
    assert "Nearest lightning" in html
    assert 'aria-label="RainViewer radar image with storm cores near home"' in html
    assert ">Weather data by RainViewer</a>" in html
    assert "Bouř" not in html
    assert "Kroup" not in html
    assert "Nejbližší" not in html
    assert "Radarový snímek" not in html


def test_czech_localizes_visible_aria_and_rainviewer_attribution() -> None:
    frame_time = 1_710_000_000
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail",
            attributes={
                "frame_time": frame_time,
                "radar_overlay": _radar_overlay(frame_time=frame_time),
            },
        ),
        language="cs",
    )

    assert "Detektor bouřek" in html
    assert 'aria-label="Radarový snímek RainViewer s bouřkovými jádry v okolí domova"' in html
    assert ">Data o počasí od RainViewer</a>" in html
    assert "Weather data by RainViewer" not in html


def test_explicit_title_override_is_preserved_for_every_language() -> None:
    states = _states("none", evidence_kind="none")

    assert "My local title" in _render(states, config={"title": "My local title"}, language="en")
    assert "My local title" in _render(states, config={"title": "My local title"}, language="cs")


@pytest.mark.parametrize("radar_status", ["stale", "degraded", "unavailable", "error"])
def test_noncurrent_radar_keeps_current_lightning_and_suppresses_radar_facts(
    radar_status: str,
) -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail_with_lightning",
            attributes={
                "selected_core_distance_km": 4.2,
                "selected_core_max_dbz": 61,
                "selected_core_area_km2": 18.0,
                "storm_approaching": True,
                "storm_eta_minutes": 6,
                "lightning_distance_km": 9.4,
                "source_status": {"radar": radar_status, "lightning": "ok"},
            },
        ),
        language="en",
    )

    assert "Lightning nearby" in html
    assert "9.4 km" in html
    assert "Possible hail" not in html
    assert "High possible hail" not in html
    assert "Nearest core" not in html
    assert "Core intensity" not in html
    assert "Core area" not in html
    assert "Approaching" not in html
    assert "Arrival" not in html
    assert "<svg" not in html


@pytest.mark.parametrize("lightning_status", ["stale", "degraded", "unavailable", "error"])
def test_noncurrent_lightning_keeps_current_radar_and_suppresses_lightning_facts(
    lightning_status: str,
) -> None:
    html = _render(
        _states(
            "warning",
            evidence_kind="radar_hail_with_lightning",
            attributes={
                "selected_core_distance_km": 12.4,
                "selected_core_max_dbz": 58,
                "storm_cores": [{"distance_km": 12.4, "bearing_degrees": 180.0}],
                "lightning_distance_km": 3.1,
                "source_status": {"radar": "ok", "lightning": lightning_status},
            },
        ),
        language="en",
    )

    assert "Possible hail" in html
    assert "12.4 km" in html
    assert "Core intensity" in html
    assert 'aria-label="Storm core positions relative to home"' in html
    assert "Nearest lightning" not in html
    assert "3.1 km" not in html
    assert "Lightning also detected" not in html
