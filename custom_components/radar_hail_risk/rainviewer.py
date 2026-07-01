"""RainViewer data helpers for frame ingestion and core detection.

This module is intentionally self-contained and testable outside Home Assistant.
It contains only helper logic plus thin async fetch helpers.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import time
from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - optional image dependency for runtime decode.
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

RAINVIEWER_API_BASE = "https://api.rainviewer.com/public"
RAINVIEWER_METADATA_ENDPOINTS = (
    "/weather-maps-api/v1/radar",
    "/weather-maps.json",
)
RAINVIEWER_COLOR_TABLE_URL = "https://www.rainviewer.com/files/rainviewer_api_colors_table.csv"
RAINVIEWER_TILE_SIZE = 512
RAINVIEWER_TILE_SCALE = "2"
RAINVIEWER_COLOR_SCHEME = "Universal Blue"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_RETRY_ATTEMPTS = 1
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25

_METADATA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_COLOR_TABLE_CACHE: dict[str, tuple[float, dict[tuple[int, int, int, int], int]]] = {}


@dataclass(frozen=True)
class AnalyzedFrame:
    """Result of one frame radar analysis."""

    frame_time: int
    max_dbz: int | None
    core50_distance_km: float | None
    core55_distance_km: float | None
    core60_distance_km: float | None
    core50_latitude: float | None
    core50_longitude: float | None
    core55_latitude: float | None
    core55_longitude: float | None
    core60_latitude: float | None
    core60_longitude: float | None
    analyzed_pixels: int


@dataclass(frozen=True)
class RadarAnalysis:
    """Aggregated analysis across selected recent frames."""

    frame_time: int | None
    frame_age_seconds: int | None
    max_dbz: int | None
    core50_distance_km: float | None
    core55_distance_km: float | None
    core60_distance_km: float | None
    selected_core_threshold_dbz: int | None
    selected_core_distance_km: float | None
    selected_core_latitude: float | None
    selected_core_longitude: float | None
    frames_analyzed: int


def _is_mapping_cached(cache: dict[str, tuple[float, Any]], key: str, ttl_seconds: int) -> bool:
    if key not in cache:
        return False
    expires_at, value = cache[key]
    if not value:
        return False
    return time.time() <= expires_at


def _cache_set_metadata(key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    _METADATA_CACHE[key] = (time.time() + ttl_seconds, payload)


def _cache_set_colors(
    key: str, lookup: dict[tuple[int, int, int, int], int], ttl_seconds: int
) -> None:
    _COLOR_TABLE_CACHE[key] = (time.time() + ttl_seconds, lookup)


def _tile_count(zoom: int) -> int:
    return 2**zoom


def _read_color_value(value: str | int | tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    if isinstance(value, tuple):
        if len(value) == 3:
            r, g, b = value
            return (r, g, b, 255)
        if len(value) == 4:
            return value
        return None

    if isinstance(value, int):
        if value < 0:
            return None
        if value <= 0xFFFFFF:
            r = (value >> 16) & 0xFF
            g = (value >> 8) & 0xFF
            b = value & 0xFF
            return (r, g, b, 255)
        if value <= 0xFFFFFFFF:
            r = (value >> 24) & 0xFF
            g = (value >> 16) & 0xFF
            b = (value >> 8) & 0xFF
            a = value & 0xFF
            return (r, g, b, a)
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    if text.startswith("#"):
        text = text[1:]
    if text.startswith("0x"):
        text = text[2:]

    if len(text) not in {6, 8}:
        return None
    if any(ch not in "0123456789abcdef" for ch in text):
        return None

    if len(text) == 6:
        r = int(text[0:2], 16)
        g = int(text[2:4], 16)
        b = int(text[4:6], 16)
        a = 255
        return (r, g, b, a)

    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    a = int(text[6:8], 16)
    return (r, g, b, a)


def dbz_from_color_value(
    color_value: str | int | tuple[int, int, int, int],
    color_lookup: dict[tuple[int, int, int, int], int] | None = None,
) -> int | None:
    """Convert a color sample to dBZ.

    Supports RGBA tuple input from image decoders and hex/int encoded values.
    """

    if color_lookup is None:
        color_lookup = {}

    color = _read_color_value(color_value)
    if color is None:
        return None
    return color_lookup.get(color)


def select_recent_frames(
    metadata: dict[str, Any],
    required_frames: int = 4,
) -> list[dict[str, Any]]:
    """Return newest N radar frames from metadata."""

    if required_frames <= 0:
        return []

    frames = metadata.get("radar", {}).get("past", [])
    if not isinstance(frames, list):
        return []

    cleaned: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        time_value = frame.get("time")
        path = frame.get("path")
        if path is None:
            continue
        if not isinstance(time_value, int):
            try:
                time_value = int(time_value)  # type: ignore[arg-type]
            except Exception:
                continue
        cleaned.append({"time": time_value, "path": path, **frame})

    cleaned.sort(key=lambda item: int(item["time"]), reverse=True)
    return cleaned[:required_frames]


def parse_color_table(content: str, scheme: str = RAINVIEWER_COLOR_SCHEME) -> dict[tuple[int, int, int, int], int]:
    """Parse the RainViewer color CSV into RGBA->dBZ mapping."""

    reader = csv.reader(io.StringIO(content))
    header = next(reader, [])
    if not header:
        return {}

    try:
        color_index = header.index(scheme)
    except ValueError:
        # Historical fallback for older or localized exports.
        color_index = min(3, len(header) - 1)

    table: dict[tuple[int, int, int, int], int] = {}
    for row in reader:
        if not row or len(row) <= color_index:
            continue
        if row[0].lower().startswith("dbz"):
            continue

        try:
            dbz = int(float(row[0]))
        except Exception:
            continue

        color_token = row[color_index].strip()
        color = _read_color_value(color_token)
        if color is None:
            continue
        r, g, b, a = color
        if a == 0:
            continue

        table[(r, g, b, a)] = dbz
    return table


async def _extract_json(response: Any) -> Any:
    if hasattr(response, "json") and callable(response.json):
        return await response.json(content_type=None)
    if hasattr(response, "text") and callable(response.text):
        text = await response.text()
        return json.loads(text)
    raw = await response.read()
    return json.loads(raw.decode("utf-8", "ignore"))


async def _extract_status(response: Any) -> int:
    if isinstance(response.status, int):
        return response.status
    return 0


async def _close_response(response: Any) -> None:
    if hasattr(response, "release") and callable(response.release):
        try:
            result = response.release()
            if callable(getattr(result, "__await__", None)):
                await result
        except Exception:
            pass


def _should_retry_status(status: int) -> bool:
    """Return true for transient HTTP statuses worth retrying."""

    return status == 0 or status == 408 or status == 429 or status >= 500


async def _sleep_between_retries(delay_seconds: float) -> None:
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)


async def _safe_get_json(
    session: Any,
    url: str,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    *,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any] | None:
    """Fetch JSON with bounded transient retry/backoff and quiet failure."""

    for attempt in range(max(retry_attempts, 0) + 1):
        response = None
        try:
            response = await session.get(url, timeout=timeout)
            status = await _extract_status(response)
            if status and status >= 400:
                if _should_retry_status(status) and attempt < retry_attempts:
                    await _sleep_between_retries(retry_backoff_seconds * (attempt + 1))
                    continue
                return None
            payload = await _extract_json(response)
            return payload if isinstance(payload, dict) else None
        except Exception:
            if attempt >= retry_attempts:
                return None
            await _sleep_between_retries(retry_backoff_seconds * (attempt + 1))
        finally:
            if response is not None:
                await _close_response(response)
    return None


async def fetch_rainviewer_color_lookup(
    session: Any,
    color_url: str = RAINVIEWER_COLOR_TABLE_URL,
    ttl_seconds: int = 24 * 3600,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> dict[tuple[int, int, int, int], int]:
    """Fetch and parse RainViewer color table, using in-memory TTL cache."""

    if _is_mapping_cached(_COLOR_TABLE_CACHE, color_url, ttl_seconds):
        return _COLOR_TABLE_CACHE[color_url][1]

    payload = await _safe_get_text(
        session,
        color_url,
        timeout=timeout,
        retry_attempts=retry_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    if payload is None:
        return {}

    lookup = parse_color_table(payload)
    _cache_set_colors(color_url, lookup, ttl_seconds)
    return lookup


async def _safe_get_text(
    session: Any,
    url: str,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    *,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> str | None:
    """Fetch text with bounded transient retry/backoff and quiet failure."""

    for attempt in range(max(retry_attempts, 0) + 1):
        response = None
        try:
            response = await session.get(url, timeout=timeout)
            status = await _extract_status(response)
            if status and status >= 400:
                if _should_retry_status(status) and attempt < retry_attempts:
                    await _sleep_between_retries(retry_backoff_seconds * (attempt + 1))
                    continue
                return None
            if hasattr(response, "text") and callable(response.text):
                return await response.text()
            data = await response.read()
            return data.decode("utf-8", "ignore")
        except Exception:
            if attempt >= retry_attempts:
                return None
            await _sleep_between_retries(retry_backoff_seconds * (attempt + 1))
        finally:
            if response is not None:
                await _close_response(response)
    return None


def _frame_is_valid(frame: Any) -> bool:
    if not isinstance(frame, dict):
        return False
    if not isinstance(frame.get("time"), (int, float, str)):
        return False
    if not frame.get("path"):
        return False
    return True


async def fetch_radar_metadata(
    session: Any,
    api_base: str = RAINVIEWER_API_BASE,
    paths: tuple[str, ...] = RAINVIEWER_METADATA_ENDPOINTS,
    ttl_seconds: int = 120,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any]:
    """Fetch RainViewer metadata with lightweight TTL caching."""

    cache_key = f"{api_base}:{','.join(paths)}"
    if _is_mapping_cached(_METADATA_CACHE, cache_key, ttl_seconds):
        return _METADATA_CACHE[cache_key][1]

    for path in paths:
        url = f"{api_base.rstrip('/')}{path}"
        payload = await _safe_get_json(
            session,
            url,
            timeout=timeout,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        if isinstance(payload, dict) and payload.get("radar"):
            _cache_set_metadata(cache_key, payload, ttl_seconds)
            return payload

    _cache_set_metadata(cache_key, {}, ttl_seconds)
    return {}


def latlon_to_global_px(lat: float, lon: float, z: int, tile_size: int = RAINVIEWER_TILE_SIZE) -> tuple[float, float]:
    n = _tile_count(z)
    x = (lon + 180.0) / 360.0 * n * tile_size
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * tile_size
    return x, y


def global_px_to_latlon(
    px: float,
    py: float,
    z: int,
    tile_size: int = RAINVIEWER_TILE_SIZE,
) -> tuple[float, float]:
    n = _tile_count(z)
    lon = px / (n * tile_size) * 360.0 - 180.0
    merc_y = math.pi * (1.0 - 2.0 * py / (n * tile_size))
    lat = math.degrees(math.atan(math.sinh(merc_y)))
    return lat, lon


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _meters_per_pixel(lat: float, zoom: int, tile_size: int = RAINVIEWER_TILE_SIZE) -> float:
    # Formula from spherical Mercator, adapted for the configured tile size.
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** (zoom + 1))


def _tile_span_for_radius(
    radius_km: float,
    lat: float,
    zoom: int,
    tile_size: int = RAINVIEWER_TILE_SIZE,
) -> int:
    if radius_km <= 0:
        return 0

    mpp = _meters_per_pixel(lat, zoom, tile_size)
    if mpp <= 0:
        return 0

    radius_px = radius_km * 1000.0 / mpp
    return max(0, math.ceil(radius_px / tile_size))


async def _fetch_tile_bytes(
    session: Any,
    url: str,
    timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    *,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> bytes | None:
    if Image is None:
        return None
    for attempt in range(max(retry_attempts, 0) + 1):
        response = None
        try:
            response = await session.get(url, timeout=timeout)
            status = await _extract_status(response)
            if status and status >= 400:
                if _should_retry_status(status) and attempt < retry_attempts:
                    await _sleep_between_retries(retry_backoff_seconds * (attempt + 1))
                    continue
                return None
            return await response.read()
        except Exception:
            if attempt >= retry_attempts:
                return None
            await _sleep_between_retries(retry_backoff_seconds * (attempt + 1))
        finally:
            if response is not None:
                await _close_response(response)
    return None


def _decode_dbz_grid(
    tile_bytes: bytes,
    color_lookup: dict[tuple[int, int, int, int], int],
) -> list[list[int | None]]:
    if Image is None:
        raise RuntimeError("Pillow is not available")

    image = Image.open(io.BytesIO(tile_bytes)).convert("RGBA")
    width, height = image.size
    rows: list[list[int | None]] = []
    if hasattr(image, "get_flattened_data"):
        flat = image.get_flattened_data()
        for y in range(height):
            row: list[int | None] = []
            for pixel in flat[y * width : (y + 1) * width]:
                if isinstance(pixel, int):
                    r = (pixel >> 24) & 0xFF
                    g = (pixel >> 16) & 0xFF
                    b = (pixel >> 8) & 0xFF
                    a = pixel & 0xFF
                else:
                    r, g, b, a = pixel
                row.append(dbz_from_color_value((r, g, b, a), color_lookup))
            rows.append(row)

    else:
        flat = list(image.getdata())
        index = 0
        for _ in range(height):
            row: list[int | None] = []
            for _ in range(width):
                row.append(dbz_from_color_value(flat[index], color_lookup))
                index += 1
            rows.append(row)
    return rows


def _analyse_dbz_grid(
    dbz_grid: list[list[int | None]],
    tile_origin_px: tuple[float, float],
    center_latitude: float,
    center_longitude: float,
    zoom: int,
    tile_size: int,
    frame_time: int,
    analysis_radius_km: float,
) -> AnalyzedFrame:
    world_x0, world_y0 = tile_origin_px
    max_dbz: int | None = None
    best50: tuple[float, float, float] | None = None
    best55: tuple[float, float, float] | None = None
    best60: tuple[float, float, float] | None = None
    analyzed_pixels = 0

    for local_y, row in enumerate(dbz_grid):
        for local_x, dbz_value in enumerate(row):
            if dbz_value is None:
                continue

            global_x = world_x0 + local_x
            global_y = world_y0 + local_y
            pixel_lat, pixel_lon = global_px_to_latlon(global_x, global_y, zoom, tile_size)
            distance = haversine_km(pixel_lat, pixel_lon, center_latitude, center_longitude)
            if distance > analysis_radius_km:
                continue

            analyzed_pixels += 1
            if max_dbz is None or dbz_value > max_dbz:
                max_dbz = dbz_value

            if dbz_value >= 50:
                if best50 is None or distance < best50[0]:
                    best50 = (distance, float(pixel_lat), float(pixel_lon))

            if dbz_value >= 55:
                if best55 is None or distance < best55[0]:
                    best55 = (distance, float(pixel_lat), float(pixel_lon))

            if dbz_value >= 60:
                if best60 is None or distance < best60[0]:
                    best60 = (distance, float(pixel_lat), float(pixel_lon))

    if best50 is not None:
        core50_distance, core50_lat, core50_lon = best50
    else:
        core50_distance, core50_lat, core50_lon = (None, None, None)

    if best55 is not None:
        core55_distance, core55_lat, core55_lon = best55
    else:
        core55_distance, core55_lat, core55_lon = (None, None, None)

    if best60 is not None:
        core60_distance, core60_lat, core60_lon = best60
    else:
        core60_distance, core60_lat, core60_lon = (None, None, None)

    return AnalyzedFrame(
        frame_time=frame_time,
        max_dbz=max_dbz,
        core50_distance_km=core50_distance,
        core55_distance_km=core55_distance,
        core60_distance_km=core60_distance,
        core50_latitude=core50_lat,
        core50_longitude=core50_lon,
        core55_latitude=core55_lat,
        core55_longitude=core55_lon,
        core60_latitude=core60_lat,
        core60_longitude=core60_lon,
        analyzed_pixels=analyzed_pixels,
    )


def _select_frame_url(
    host: str,
    path: str,
    zoom: int,
    x: int,
    y: int,
    tile_size: int = RAINVIEWER_TILE_SIZE,
    scale: str = RAINVIEWER_TILE_SCALE,
) -> str:
    return f"{host.rstrip('/')}{path}/{tile_size}/{zoom}/{x}/{y}/{scale}/1_1.png"


async def analyze_single_radar_frame(
    session: Any,
    host: str,
    frame: dict[str, Any],
    center_latitude: float,
    center_longitude: float,
    analysis_radius_km: float,
    zoom: int,
    color_lookup: dict[tuple[int, int, int, int], int],
    tile_size: int = RAINVIEWER_TILE_SIZE,
    timeout: int = 20,
) -> AnalyzedFrame | None:
    """Analyze one frame and return nearest 55+/60+ core data."""

    if not _frame_is_valid(frame):
        return None
    if analysis_radius_km <= 0:
        return None
    if Image is None:
        return None

    try:
        frame_time = int(frame["time"])
    except Exception:
        return None
    path = str(frame["path"])

    center_x, center_y = latlon_to_global_px(center_latitude, center_longitude, zoom, tile_size)
    center_tx = int(center_x // tile_size)
    center_ty = int(center_y // tile_size)
    span = _tile_span_for_radius(analysis_radius_km, center_latitude, zoom, tile_size)
    tile_count = _tile_count(zoom)

    frame_pixels_analysed = 0
    max_dbz: int | None = None
    best50: tuple[float, float, float] | None = None
    best55: tuple[float, float, float] | None = None
    best60: tuple[float, float, float] | None = None

    for tile_y in range(center_ty - span, center_ty + span + 1):
        if tile_y < 0 or tile_y >= tile_count:
            continue

        for tile_x in range(center_tx - span, center_tx + span + 1):
            wrapped_x = tile_x % tile_count
            tile_url = _select_frame_url(host, path, zoom, wrapped_x, tile_y, tile_size)
            tile_bytes = await _fetch_tile_bytes(session, tile_url, timeout=timeout)
            if not tile_bytes:
                continue

            try:
                tile_grid = _decode_dbz_grid(tile_bytes, color_lookup)
            except Exception:
                continue

            tile_origin_x = wrapped_x * tile_size
            tile_origin_y = tile_y * tile_size
            if wrapped_x != tile_x:
                # Keep deterministic offset for longitude-wrap edges.
                tile_origin_x = (tile_x * tile_size)

            frame_result = _analyse_dbz_grid(
                tile_grid,
                (tile_origin_x, tile_origin_y),
                center_latitude,
                center_longitude,
                zoom,
                tile_size,
                frame_time,
                analysis_radius_km,
            )

            frame_pixels_analysed += frame_result.analyzed_pixels
            if frame_result.max_dbz is not None:
                max_dbz = frame_result.max_dbz if max_dbz is None else max(max_dbz, frame_result.max_dbz)
            if frame_result.core50_distance_km is not None:
                candidate50 = (
                    frame_result.core50_distance_km,
                    float(frame_result.core50_latitude),
                    float(frame_result.core50_longitude),
                )
                if best50 is None or candidate50[0] < best50[0]:
                    best50 = candidate50
            if frame_result.core55_distance_km is not None:
                candidate55 = (
                    frame_result.core55_distance_km,
                    float(frame_result.core55_latitude),
                    float(frame_result.core55_longitude),
                )
                if best55 is None or candidate55[0] < best55[0]:
                    best55 = candidate55
            if frame_result.core60_distance_km is not None:
                candidate60 = (
                    frame_result.core60_distance_km,
                    float(frame_result.core60_latitude),
                    float(frame_result.core60_longitude),
                )
                if best60 is None or candidate60[0] < best60[0]:
                    best60 = candidate60

    if frame_pixels_analysed == 0:
        return None

    core50_distance, core50_lat, core50_lon = best50 if best50 is not None else (None, None, None)
    core55_distance, core55_lat, core55_lon = best55 if best55 is not None else (None, None, None)
    core60_distance, core60_lat, core60_lon = best60 if best60 is not None else (None, None, None)

    return AnalyzedFrame(
        frame_time=frame_time,
        max_dbz=max_dbz,
        core50_distance_km=core50_distance,
        core55_distance_km=core55_distance,
        core60_distance_km=core60_distance,
        core50_latitude=core50_lat,
        core50_longitude=core50_lon,
        core55_latitude=core55_lat,
        core55_longitude=core55_lon,
        core60_latitude=core60_lat,
        core60_longitude=core60_lon,
        analyzed_pixels=frame_pixels_analysed,
    )


async def analyze_recent_frames(
    session: Any,
    metadata: dict[str, Any],
    center_latitude: float,
    center_longitude: float,
    *,
    analysis_radius_km: float,
    required_frames: int = 4,
    zoom: int = 7,
    color_lookup: dict[tuple[int, int, int, int], int] | None = None,
    color_table_session: Any | None = None,
    now: int | None = None,
) -> RadarAnalysis | None:
    """Run core detection on the latest metadata frames.

    Returns None when no current analyzable coverage is available.
    """

    if now is None:
        now = int(time.time())

    selected = select_recent_frames(metadata, required_frames=required_frames)
    if not selected:
        return None

    host = metadata.get("host")
    if not isinstance(host, str):
        return None

    if color_lookup is None:
        if color_table_session is None:
            color_table_session = session
        color_lookup = await fetch_rainviewer_color_lookup(color_table_session)
        if not color_lookup:
            return None

    frame_results: list[AnalyzedFrame] = []
    for frame in selected:
        result = await analyze_single_radar_frame(
            session,
            host,
            frame,
            center_latitude,
            center_longitude,
            analysis_radius_km,
            zoom,
            color_lookup,
        )
        if result is None or result.analyzed_pixels == 0:
            continue
        frame_results.append(result)

    if not frame_results:
        return None

    # Keep newest-to-oldest in select_recent_frames; use newest valid frame for the
    # user-facing current risk. Older frames are analyzed for robustness/coverage, but
    # their historic max dBZ must not keep WARNING active after the latest radar frame
    # no longer contains a hail core.
    latest = frame_results[0]
    max_dbz = latest.max_dbz
    if max_dbz is None:
        return None

    if latest.core60_distance_km is not None:
        selected_threshold = 60
        selected_distance = latest.core60_distance_km
        selected_lat = latest.core60_latitude
        selected_lon = latest.core60_longitude
    elif latest.core55_distance_km is not None:
        selected_threshold = 55
        selected_distance = latest.core55_distance_km
        selected_lat = latest.core55_latitude
        selected_lon = latest.core55_longitude
    elif latest.core50_distance_km is not None:
        selected_threshold = 50
        selected_distance = latest.core50_distance_km
        selected_lat = latest.core50_latitude
        selected_lon = latest.core50_longitude
    else:
        selected_threshold = None
        selected_distance = None
        selected_lat = None
        selected_lon = None

    frame_age_seconds = now - latest.frame_time
    if frame_age_seconds < 0:
        frame_age_seconds = 0

    return RadarAnalysis(
        frame_time=latest.frame_time,
        frame_age_seconds=frame_age_seconds,
        max_dbz=max_dbz,
        core50_distance_km=latest.core50_distance_km,
        core55_distance_km=latest.core55_distance_km,
        core60_distance_km=latest.core60_distance_km,
        selected_core_threshold_dbz=selected_threshold,
        selected_core_distance_km=selected_distance,
        selected_core_latitude=selected_lat,
        selected_core_longitude=selected_lon,
        frames_analyzed=len(frame_results),
    )
