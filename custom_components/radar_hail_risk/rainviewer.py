"""RainViewer data helpers for frame ingestion and core detection.

This module is intentionally self-contained and testable outside Home Assistant.
It contains only helper logic plus thin async fetch helpers.
"""

from __future__ import annotations

import asyncio
import csv
import functools
import io
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar
from urllib.parse import urlsplit

from .async_utils import drain_future

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
RAINVIEWER_COLOR_SCHEME_ID = 2
RAINVIEWER_TILE_OPTIONS = "1_1"
RAINVIEWER_MAX_NATIVE_ZOOM = 7
RAINVIEWER_MAX_HOST_LENGTH = 267
RAINVIEWER_MAX_PATH_LENGTH = 80
RAINVIEWER_MAX_FRAME_ID_LENGTH = 64
RAINVIEWER_MAX_OPTIONS_LENGTH = 32
RAINVIEWER_MAX_TILE_TEMPLATE_LENGTH = 512
RADAR_OVERLAY_CORE_LIMIT = 12
RAINVIEWER_COLOR_SCHEME = "Universal Blue"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_RETRY_ATTEMPTS = 1
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25
MAX_PARALLEL_TILE_FETCHES = 4
MAX_TRACK_SPEED_KMH = 180.0
MAX_TRACK_INTENSITY_DELTA_DBZ = 15
MIN_TRACK_DISTANCE_KM = 2.0
MIN_APPROACHING_RADIAL_SPEED_KMH = 10.0
MAX_ACTIONABLE_ETA_MINUTES = 180

_T = TypeVar("_T")

_METADATA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_COLOR_TABLE_CACHE: dict[str, tuple[float, dict[tuple[int, int, int, int], int]]] = {}


async def _run_in_executor_and_drain(
    function: Callable[..., _T],
    /,
    *args: Any,
    **kwargs: Any,
) -> _T:
    """Run CPU work off-loop and wait for the worker before propagating cancellation."""

    loop = asyncio.get_running_loop()
    worker = loop.run_in_executor(None, functools.partial(function, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await drain_future(worker)
        raise


@dataclass(frozen=True)
class StormCore:
    """Connected radar-core object above one dBZ threshold."""

    threshold_dbz: int
    max_dbz: int
    area_km2: float
    centroid_latitude: float
    centroid_longitude: float
    nearest_latitude: float
    nearest_longitude: float
    distance_km: float
    pixel_count: int
    pixel_keys: frozenset[tuple[int, int]] = frozenset()


@dataclass(frozen=True)
class StormMotion:
    """Motion/trend estimate for the selected storm core."""

    bearing: float | None
    speed_kmh: float | None
    approaching: bool | None
    eta_minutes: int | None
    dbz_trend: str | None
    distance_trend: str | None


@dataclass(frozen=True)
class _CoreTrackSample:
    """One normalized component sample used for temporal matching."""

    frame_time: int
    threshold_dbz: int
    max_dbz: int
    distance_km: float
    latitude: float
    longitude: float
    is_selected: bool


@dataclass(frozen=True)
class AnalyzedFrame:
    """Result of one frame radar analysis."""

    frame_time: int
    max_dbz: int | None
    max_core_dbz: int | None
    core50_distance_km: float | None
    core55_distance_km: float | None
    core60_distance_km: float | None
    core_watch_distance_km: float | None
    core_warning_distance_km: float | None
    core_urgent_distance_km: float | None
    core50_latitude: float | None
    core50_longitude: float | None
    core55_latitude: float | None
    core55_longitude: float | None
    core60_latitude: float | None
    core60_longitude: float | None
    core_watch_latitude: float | None
    core_watch_longitude: float | None
    core_warning_latitude: float | None
    core_warning_longitude: float | None
    core_urgent_latitude: float | None
    core_urgent_longitude: float | None
    selected_core_area_km2: float | None
    selected_core_pixel_count: int | None
    selected_core_max_dbz: int | None
    selected_core_threshold_dbz: int | None
    selected_core_distance_km: float | None
    selected_core_latitude: float | None
    selected_core_longitude: float | None
    selected_core_centroid_latitude: float | None
    selected_core_centroid_longitude: float | None
    storm_cores: tuple[dict[str, int | float], ...]
    core_count: int
    analyzed_pixels: int
    frame_path: str = ""
    overlay_cores: tuple[dict[str, int | float], ...] = ()
    overlay_selected_core_forced_included: bool = False


@dataclass(frozen=True)
class RadarAnalysis:
    """Aggregated analysis across selected recent frames."""

    frame_time: int | None
    frame_age_seconds: int | None
    max_dbz: int | None
    max_core_dbz: int | None
    core50_distance_km: float | None
    core55_distance_km: float | None
    core60_distance_km: float | None
    core_watch_distance_km: float | None
    core_warning_distance_km: float | None
    core_urgent_distance_km: float | None
    selected_core_threshold_dbz: int | None
    selected_core_distance_km: float | None
    selected_core_latitude: float | None
    selected_core_longitude: float | None
    selected_core_area_km2: float | None
    selected_core_pixel_count: int | None
    selected_core_max_dbz: int | None
    storm_cores: tuple[dict[str, int | float], ...]
    core_count: int
    storm_motion_bearing: float | None
    storm_motion_speed_kmh: float | None
    storm_approaching: bool | None
    storm_eta_minutes: int | None
    dbz_trend: str | None
    distance_trend: str | None
    frames_analyzed: int
    frame_host: str
    frame_path: str
    metadata_generated_time: int | None
    tile_size: int
    display_zoom: int
    max_native_zoom: int
    color_scheme_id: int
    tile_options: str
    selected_core_centroid_latitude: float | None
    selected_core_centroid_longitude: float | None
    overlay_cores: tuple[dict[str, int | float], ...] = ()
    overlay_selected_core_forced_included: bool = False


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


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return initial bearing from point 1 to point 2 in degrees."""

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return round((math.degrees(math.atan2(y, x)) + 360) % 360, 1)


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


def _tile_points_from_bytes(
    tile_bytes: bytes,
    color_lookup: dict[tuple[int, int, int, int], int],
    *,
    tile_x: int,
    wrapped_x: int,
    tile_y: int,
    center_latitude: float,
    center_longitude: float,
    analysis_radius_km: float,
    zoom: int,
    tile_size: int,
) -> dict[tuple[int, int], tuple[int, float, float, float]]:
    """Decode one tile and collect in-radius radar points in a worker thread."""

    tile_grid = _decode_dbz_grid(tile_bytes, color_lookup)
    tile_origin_x = wrapped_x * tile_size
    tile_origin_y = tile_y * tile_size
    if wrapped_x != tile_x:
        tile_origin_x = tile_x * tile_size

    points: dict[tuple[int, int], tuple[int, float, float, float]] = {}
    for local_y, row in enumerate(tile_grid):
        for local_x, dbz_value in enumerate(row):
            if dbz_value is None:
                continue
            global_x = tile_origin_x + local_x
            global_y = tile_origin_y + local_y
            pixel_lat, pixel_lon = global_px_to_latlon(global_x, global_y, zoom, tile_size)
            distance = haversine_km(
                pixel_lat,
                pixel_lon,
                center_latitude,
                center_longitude,
            )
            if distance > analysis_radius_km:
                continue
            points[(int(global_x), int(global_y))] = (
                int(dbz_value),
                float(pixel_lat),
                float(pixel_lon),
                float(distance),
            )
    return points


def _component_cores_from_points(
    points: dict[tuple[int, int], tuple[int, float, float, float]],
    *,
    threshold_dbz: int,
    pixel_area_km2: float,
    min_core_pixels: int = 1,
) -> list[StormCore]:
    """Build connected storm-core components for one threshold.

    Points are keyed by global pixel coordinate and hold (dbz, lat, lon, distance_km).
    Eight-neighbour connectivity keeps diagonal radar blobs together.
    """

    eligible = {key for key, (dbz, *_rest) in points.items() if dbz >= threshold_dbz}
    cores: list[StormCore] = []
    while eligible:
        start = eligible.pop()
        stack = [start]
        component = [start]
        while stack:
            x, y = stack.pop()
            for nx in range(x - 1, x + 2):
                for ny in range(y - 1, y + 2):
                    if nx == x and ny == y:
                        continue
                    neighbour = (nx, ny)
                    if neighbour not in eligible:
                        continue
                    eligible.remove(neighbour)
                    stack.append(neighbour)
                    component.append(neighbour)

        samples = [points[key] for key in component]
        if len(samples) < min_core_pixels:
            continue
        max_dbz = max(sample[0] for sample in samples)
        nearest = min(samples, key=lambda sample: sample[3])
        centroid_lat = sum(sample[1] for sample in samples) / len(samples)
        centroid_lon = sum(sample[2] for sample in samples) / len(samples)
        cores.append(
            StormCore(
                threshold_dbz=threshold_dbz,
                max_dbz=max_dbz,
                area_km2=round(len(samples) * pixel_area_km2, 3),
                centroid_latitude=float(centroid_lat),
                centroid_longitude=float(centroid_lon),
                nearest_latitude=float(nearest[1]),
                nearest_longitude=float(nearest[2]),
                distance_km=float(nearest[3]),
                pixel_count=len(samples),
                pixel_keys=frozenset(component),
            )
        )

    cores.sort(key=lambda core: (core.distance_km, -core.max_dbz, -core.pixel_count))
    return cores


def _storm_core_summaries(
    cores: list[StormCore],
    *,
    center_latitude: float,
    center_longitude: float,
    limit: int = 8,
    selected_core: StormCore | None = None,
    warning_cores: list[StormCore] | None = None,
    urgent_cores: list[StormCore] | None = None,
) -> tuple[tuple[dict[str, int | float], ...], bool]:
    """Return a compact top-N core list safe for HA attributes and Lovelace."""

    def contains(parent: StormCore, child: StormCore) -> bool:
        return bool(child.pixel_keys) and child.pixel_keys.issubset(parent.pixel_keys)

    def nearest_nested_distance(
        parent: StormCore, nested_cores: list[StormCore] | None
    ) -> float | None:
        distances = [
            core.distance_km for core in nested_cores or () if contains(parent, core)
        ]
        return min(distances, default=None)

    ranked = sorted(cores, key=lambda item: (item.distance_km, -item.max_dbz, -item.pixel_count))
    indexed_cores = list(enumerate(ranked, start=1))
    selected_item: tuple[int, StormCore] | None = None
    if selected_core is not None:
        selected_item = next(
            (
                item
                for item in indexed_cores
                if contains(item[1], selected_core)
            ),
            None,
        )

    selected_forced = False
    rendered = indexed_cores[:limit]
    if selected_item is not None and selected_item not in rendered and rendered:
        rendered[-1] = selected_item
        selected_forced = True

    summaries: list[dict[str, int | float]] = []
    for index, core in rendered:
        summary: dict[str, int | float] = {
            "index": index,
            "threshold_dbz": int(core.threshold_dbz),
            "max_dbz": int(core.max_dbz),
            "distance_km": round(float(core.distance_km), 3),
            "bearing_degrees": round(
                bearing_degrees(
                    center_latitude,
                    center_longitude,
                    core.nearest_latitude,
                    core.nearest_longitude,
                ),
                1,
            ),
            "latitude": round(float(core.nearest_latitude), 6),
            "longitude": round(float(core.nearest_longitude), 6),
            "centroid_latitude": round(float(core.centroid_latitude), 6),
            "centroid_longitude": round(float(core.centroid_longitude), 6),
            "area_km2": round(float(core.area_km2), 3),
            "pixel_count": int(core.pixel_count),
        }
        if selected_core is not None:
            summary["selected"] = selected_item is not None and index == selected_item[0]
            warning_distance = nearest_nested_distance(core, warning_cores)
            urgent_distance = nearest_nested_distance(core, urgent_cores)
            if warning_distance is not None:
                summary["warning_distance_km"] = round(float(warning_distance), 3)
            if urgent_distance is not None:
                summary["urgent_distance_km"] = round(float(urgent_distance), 3)
        summaries.append(summary)
    return tuple(summaries), selected_forced


def _analyse_dbz_grid(
    points: dict[tuple[int, int], tuple[int, float, float, float]],
    center_latitude: float,
    center_longitude: float,
    zoom: int,
    tile_size: int,
    frame_time: int,
    frame_path: str,
    *,
    core_watch_dbz: int,
    core_warning_dbz: int,
    core_urgent_dbz: int,
    min_core_pixels: int = 1,
) -> AnalyzedFrame:
    analyzed_pixels = len(points)
    if not points:
        return AnalyzedFrame(
            frame_time=frame_time,
            frame_path=frame_path,
            max_dbz=None,
            max_core_dbz=None,
            core50_distance_km=None,
            core55_distance_km=None,
            core60_distance_km=None,
            core_watch_distance_km=None,
            core_warning_distance_km=None,
            core_urgent_distance_km=None,
            core50_latitude=None,
            core50_longitude=None,
            core55_latitude=None,
            core55_longitude=None,
            core60_latitude=None,
            core60_longitude=None,
            core_watch_latitude=None,
            core_watch_longitude=None,
            core_warning_latitude=None,
            core_warning_longitude=None,
            core_urgent_latitude=None,
            core_urgent_longitude=None,
            selected_core_area_km2=None,
            selected_core_pixel_count=None,
            selected_core_max_dbz=None,
            selected_core_threshold_dbz=None,
            selected_core_distance_km=None,
            selected_core_latitude=None,
            selected_core_longitude=None,
            selected_core_centroid_latitude=None,
            selected_core_centroid_longitude=None,
            storm_cores=(),
            core_count=0,
            analyzed_pixels=0,
        )

    max_dbz = max(int(sample[0]) for sample in points.values())
    min_core_pixels = max(1, int(min_core_pixels))

    def sort_cores(cores: list[StormCore]) -> list[StormCore]:
        return sorted(
            cores,
            key=lambda core: (
                core.distance_km,
                -core.max_dbz,
                -core.pixel_count,
            ),
        )

    def best_core(cores: list[StormCore]) -> tuple[float, float, float] | None:
        if not cores:
            return None
        core = sort_cores(cores)[0]
        return (
            float(core.distance_km),
            float(core.nearest_latitude),
            float(core.nearest_longitude),
        )

    pixel_area_km2 = (_meters_per_pixel(center_latitude, zoom, tile_size) / 1000) ** 2
    # Keep the configured hail-oriented watch threshold authoritative, but detect a
    # narrow five-dBZ storm band below it as a connected component too.  This lets
    # the risk model surface 46-49 dBZ storm activity as WATCH without promoting
    # isolated raw pixels or weakening WARNING/URGENT hail thresholds.
    near_watch_dbz = max(0, core_watch_dbz - 5)
    cores_near_watch = _component_cores_from_points(
        points,
        threshold_dbz=near_watch_dbz,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )
    cores_watch = _component_cores_from_points(
        points,
        threshold_dbz=core_watch_dbz,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )
    cores_warning = _component_cores_from_points(
        points,
        threshold_dbz=core_warning_dbz,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )
    cores_urgent = _component_cores_from_points(
        points,
        threshold_dbz=core_urgent_dbz,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )
    cores50 = _component_cores_from_points(
        points,
        threshold_dbz=50,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )
    cores55 = _component_cores_from_points(
        points,
        threshold_dbz=55,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )
    cores60 = _component_cores_from_points(
        points,
        threshold_dbz=60,
        pixel_area_km2=pixel_area_km2,
        min_core_pixels=min_core_pixels,
    )

    best50 = best_core(cores50)
    best55 = best_core(cores55)
    best60 = best_core(cores60)
    watch_cores = cores_watch or cores_near_watch
    best_watch = best_core(watch_cores)
    best_warning = best_core(cores_warning)
    best_urgent = best_core(cores_urgent)

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

    if best_watch is not None:
        core_watch_distance, core_watch_lat, core_watch_lon = best_watch
    else:
        core_watch_distance, core_watch_lat, core_watch_lon = (None, None, None)
    if best_warning is not None:
        core_warning_distance, core_warning_lat, core_warning_lon = best_warning
    else:
        core_warning_distance, core_warning_lat, core_warning_lon = (None, None, None)
    if best_urgent is not None:
        core_urgent_distance, core_urgent_lat, core_urgent_lon = best_urgent
    else:
        core_urgent_distance, core_urgent_lat, core_urgent_lon = (None, None, None)

    selected_core = (cores_urgent or cores_warning or watch_cores or [None])[0]
    if selected_core is None:
        selected_area = None
        selected_pixels = None
        selected_max_dbz = None
        max_core_dbz = None
        selected_threshold = None
        selected_distance = None
        selected_lat = None
        selected_lon = None
        selected_centroid_lat = None
        selected_centroid_lon = None
    else:
        selected_area = selected_core.area_km2
        selected_pixels = selected_core.pixel_count
        selected_max_dbz = selected_core.max_dbz
        max_core_dbz = int(selected_core.max_dbz)
        selected_threshold = selected_core.threshold_dbz
        selected_distance = selected_core.distance_km
        selected_lat = selected_core.nearest_latitude
        selected_lon = selected_core.nearest_longitude
        selected_centroid_lat = selected_core.centroid_latitude
        selected_centroid_lon = selected_core.centroid_longitude

    storm_cores, _ = _storm_core_summaries(
        watch_cores,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
    )
    overlay_cores, overlay_selected_core_forced_included = _storm_core_summaries(
        watch_cores,
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        limit=RADAR_OVERLAY_CORE_LIMIT,
        selected_core=selected_core,
        warning_cores=cores_warning,
        urgent_cores=cores_urgent,
    )

    return AnalyzedFrame(
        frame_time=frame_time,
        frame_path=frame_path,
        max_dbz=max_dbz,
        max_core_dbz=max_core_dbz,
        core50_distance_km=core50_distance,
        core55_distance_km=core55_distance,
        core60_distance_km=core60_distance,
        core_watch_distance_km=core_watch_distance,
        core_warning_distance_km=core_warning_distance,
        core_urgent_distance_km=core_urgent_distance,
        core50_latitude=core50_lat,
        core50_longitude=core50_lon,
        core55_latitude=core55_lat,
        core55_longitude=core55_lon,
        core60_latitude=core60_lat,
        core60_longitude=core60_lon,
        core_watch_latitude=core_watch_lat,
        core_watch_longitude=core_watch_lon,
        core_warning_latitude=core_warning_lat,
        core_warning_longitude=core_warning_lon,
        core_urgent_latitude=core_urgent_lat,
        core_urgent_longitude=core_urgent_lon,
        selected_core_area_km2=selected_area,
        selected_core_pixel_count=selected_pixels,
        selected_core_max_dbz=selected_max_dbz,
        selected_core_threshold_dbz=selected_threshold,
        selected_core_distance_km=selected_distance,
        selected_core_latitude=selected_lat,
        selected_core_longitude=selected_lon,
        selected_core_centroid_latitude=selected_centroid_lat,
        selected_core_centroid_longitude=selected_centroid_lon,
        storm_cores=storm_cores,
        core_count=len(watch_cores),
        analyzed_pixels=analyzed_pixels,
        overlay_cores=overlay_cores,
        overlay_selected_core_forced_included=overlay_selected_core_forced_included,
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


def build_rainviewer_tile_url_template(
    host: Any,
    path: Any,
    *,
    tile_size: int = RAINVIEWER_TILE_SIZE,
    color_scheme_id: int = RAINVIEWER_COLOR_SCHEME_ID,
    options: str = RAINVIEWER_TILE_OPTIONS,
) -> str | None:
    """Build a constrained HTTPS RainViewer XYZ tile template."""

    if tile_size != RAINVIEWER_TILE_SIZE:
        return None
    if not isinstance(host, str) or not isinstance(path, str):
        return None
    if (
        not host
        or len(host) > RAINVIEWER_MAX_HOST_LENGTH
        or not path
        or len(path) > RAINVIEWER_MAX_PATH_LENGTH
    ):
        return None
    if any(character.isspace() or ord(character) < 32 for character in (*host, *path)):
        return None
    if any(character in host + path for character in "{}"):
        return None

    parsed_host = urlsplit(host)
    try:
        parsed_host.port
    except ValueError:
        return None
    if (
        parsed_host.scheme != "https"
        or not parsed_host.hostname
        or parsed_host.username is not None
        or parsed_host.password is not None
        or parsed_host.path not in {"", "/"}
        or parsed_host.query
        or parsed_host.fragment
        or "\\" in parsed_host.netloc
    ):
        return None
    labels = parsed_host.hostname.split(".")
    if any(
        not label
        or label.startswith("-")
        or label.endswith("-")
        or len(label) > 63
        or not label.isascii()
        or any(not (character.isalnum() or character == "-") for character in label)
        for label in labels
    ):
        return None
    hostname = parsed_host.hostname.lower()
    if (
        hostname != "rainviewer.com"
        and not hostname.endswith(".rainviewer.com")
    ) or parsed_host.port not in {None, 443}:
        return None
    if "?" in path or "#" in path or "\\" in path:
        return None

    path_segments = path.strip("/").split("/")
    if not path_segments or any(
        not segment
        or segment in {".", ".."}
        or any(
            not character.isascii()
            or not (character.isalnum() or character in {"-", "_", "."})
            for character in segment
        )
        for segment in path_segments
    ):
        return None
    if (
        len(path_segments) != 3
        or path_segments[:2] != ["v2", "radar"]
        or not 1 <= len(path_segments[2]) <= RAINVIEWER_MAX_FRAME_ID_LENGTH
        or not path_segments[2][0].isascii()
        or not path_segments[2][0].isalnum()
        or any(
            not character.isascii()
            or not (character.isalnum() or character in {"-", "_"})
            for character in path_segments[2][1:]
        )
    ):
        return None
    normalized_path = "/" + "/".join(path_segments)
    try:
        normalized_color = int(color_scheme_id)
    except (TypeError, ValueError):
        return None
    if not 0 <= normalized_color <= 255:
        return None
    normalized_options = str(options)
    if not 1 <= len(normalized_options) <= RAINVIEWER_MAX_OPTIONS_LENGTH or any(
        character.isspace() or not (character.isalnum() or character == "_")
        for character in normalized_options
    ):
        return None

    origin = f"https://{parsed_host.netloc}"
    tile_template = (
        f"{origin}{normalized_path}/{RAINVIEWER_TILE_SIZE}/"
        f"{{z}}/{{x}}/{{y}}/{normalized_color}/{normalized_options}.png"
    )
    return (
        tile_template
        if len(tile_template) <= RAINVIEWER_MAX_TILE_TEMPLATE_LENGTH
        else None
    )


async def analyze_single_radar_frame(
    session: Any,
    host: str,
    frame: dict[str, Any],
    center_latitude: float,
    center_longitude: float,
    analysis_radius_km: float,
    zoom: int,
    color_lookup: dict[tuple[int, int, int, int], int],
    *,
    core_watch_dbz: int = 50,
    core_warning_dbz: int = 55,
    core_urgent_dbz: int = 60,
    min_core_pixels: int = 1,
    tile_size: int = RAINVIEWER_TILE_SIZE,
    timeout: int = 20,
) -> AnalyzedFrame | None:
    """Analyze one frame and return nearest core data."""

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

    tile_specs: list[tuple[int, int, int, str]] = []
    for tile_y in range(center_ty - span, center_ty + span + 1):
        if tile_y < 0 or tile_y >= tile_count:
            continue
        for tile_x in range(center_tx - span, center_tx + span + 1):
            wrapped_x = tile_x % tile_count
            tile_url = _select_frame_url(host, path, zoom, wrapped_x, tile_y, tile_size)
            tile_specs.append((tile_x, wrapped_x, tile_y, tile_url))

    fetch_limit = asyncio.Semaphore(MAX_PARALLEL_TILE_FETCHES)

    async def fetch_tile_points(
        spec: tuple[int, int, int, str],
    ) -> dict[tuple[int, int], tuple[int, float, float, float]]:
        tile_x, wrapped_x, tile_y, tile_url = spec
        async with fetch_limit:
            tile_bytes = await _fetch_tile_bytes(session, tile_url, timeout=timeout)
            if not tile_bytes:
                return {}
            try:
                return await _run_in_executor_and_drain(
                    _tile_points_from_bytes,
                    tile_bytes,
                    color_lookup,
                    tile_x=tile_x,
                    wrapped_x=wrapped_x,
                    tile_y=tile_y,
                    center_latitude=center_latitude,
                    center_longitude=center_longitude,
                    analysis_radius_km=analysis_radius_km,
                    zoom=zoom,
                    tile_size=tile_size,
                )
            except Exception:
                return {}

    tile_tasks = [asyncio.create_task(fetch_tile_points(spec)) for spec in tile_specs]
    try:
        tile_point_maps = await asyncio.gather(*tile_tasks)
    except asyncio.CancelledError:
        await drain_future(asyncio.gather(*tile_tasks, return_exceptions=True))
        raise
    except BaseException:
        unfinished = [task for task in tile_tasks if not task.done()]
        for task in unfinished:
            task.cancel()
        if unfinished:
            cleanup = asyncio.gather(*tile_tasks, return_exceptions=True)
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await drain_future(cleanup)
                raise
        raise

    points: dict[tuple[int, int], tuple[int, float, float, float]] = {}
    for tile_points in tile_point_maps:
        points.update(tile_points)

    if not points:
        return None

    return await _run_in_executor_and_drain(
        _analyse_dbz_grid,
        points,
        center_latitude,
        center_longitude,
        zoom,
        tile_size,
        frame_time,
        path,
        core_watch_dbz=core_watch_dbz,
        core_warning_dbz=core_warning_dbz,
        core_urgent_dbz=core_urgent_dbz,
        min_core_pixels=min_core_pixels,
    )


def _selected_core_sample(frame: AnalyzedFrame) -> tuple[int, float, float, float] | None:
    """Return threshold, distance, lat, lon for the selected strongest core in a frame."""

    if (
        frame.selected_core_threshold_dbz is not None
        and frame.selected_core_distance_km is not None
        and frame.selected_core_latitude is not None
        and frame.selected_core_longitude is not None
    ):
        return (
            int(frame.selected_core_threshold_dbz),
            float(frame.selected_core_distance_km),
            float(frame.selected_core_latitude),
            float(frame.selected_core_longitude),
        )
    if (
        frame.core60_distance_km is not None
        and frame.core60_latitude is not None
        and frame.core60_longitude is not None
    ):
        return (60, frame.core60_distance_km, frame.core60_latitude, frame.core60_longitude)
    if (
        frame.core55_distance_km is not None
        and frame.core55_latitude is not None
        and frame.core55_longitude is not None
    ):
        return (55, frame.core55_distance_km, frame.core55_latitude, frame.core55_longitude)
    if (
        frame.core50_distance_km is not None
        and frame.core50_latitude is not None
        and frame.core50_longitude is not None
    ):
        return (50, frame.core50_distance_km, frame.core50_latitude, frame.core50_longitude)
    return None


def _trend_from_delta(delta: float, *, deadband: float, positive: str, negative: str) -> str:
    if delta > deadband:
        return positive
    if delta < -deadband:
        return negative
    return "stable"


def _component_samples(frame: AnalyzedFrame) -> list[_CoreTrackSample]:
    """Normalize the frame's component summaries for matching."""

    samples: list[_CoreTrackSample] = []
    for core in frame.storm_cores:
        try:
            samples.append(
                _CoreTrackSample(
                    frame_time=frame.frame_time,
                    threshold_dbz=int(core["threshold_dbz"]),
                    max_dbz=int(core["max_dbz"]),
                    distance_km=float(core["distance_km"]),
                    latitude=float(
                        core["centroid_latitude"]
                        if "centroid_latitude" in core
                        else core["latitude"]
                    ),
                    longitude=float(
                        core["centroid_longitude"]
                        if "centroid_longitude" in core
                        else core["longitude"]
                    ),
                    is_selected=False,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return samples


def _selected_track_sample(frame: AnalyzedFrame) -> _CoreTrackSample | None:
    """Return the selected component's own tracking sample."""

    selected = _selected_core_sample(frame)
    if selected is None:
        return None
    selected_threshold, selected_distance, selected_lat, selected_lon = selected
    selected_intensity = int(frame.selected_core_max_dbz or frame.max_core_dbz or frame.max_dbz or 0)
    return _CoreTrackSample(
        frame_time=frame.frame_time,
        threshold_dbz=selected_threshold,
        max_dbz=selected_intensity,
        distance_km=selected_distance,
        latitude=float(
            frame.selected_core_centroid_latitude
            if frame.selected_core_centroid_latitude is not None
            else selected_lat
        ),
        longitude=float(
            frame.selected_core_centroid_longitude
            if frame.selected_core_centroid_longitude is not None
            else selected_lon
        ),
        is_selected=True,
    )


def _tracked_core_samples(frame_results: list[AnalyzedFrame]) -> list[_CoreTrackSample]:
    """Match the selected latest component backwards through available frames."""

    if not frame_results:
        return []
    latest = _selected_track_sample(frame_results[0])
    if latest is None:
        return []

    track = [latest]
    reference = latest
    for frame in frame_results[1:]:
        delta_seconds = reference.frame_time - frame.frame_time
        if delta_seconds <= 0:
            continue
        max_distance_km = max(
            MIN_TRACK_DISTANCE_KM,
            MAX_TRACK_SPEED_KMH * delta_seconds / 3600,
        )
        candidates: list[tuple[float, _CoreTrackSample]] = []
        frame_candidates = _component_samples(frame)
        selected_candidate = _selected_track_sample(frame)
        if selected_candidate is not None:
            frame_candidates.append(selected_candidate)
        for candidate in frame_candidates:
            if candidate.threshold_dbz != reference.threshold_dbz and not (
                candidate.is_selected and reference.is_selected
            ):
                continue
            intensity_delta = abs(candidate.max_dbz - reference.max_dbz)
            if intensity_delta > MAX_TRACK_INTENSITY_DELTA_DBZ:
                continue
            centroid_distance = haversine_km(
                candidate.latitude,
                candidate.longitude,
                reference.latitude,
                reference.longitude,
            )
            if centroid_distance > max_distance_km:
                continue
            score = (
                centroid_distance / max_distance_km
                + intensity_delta / MAX_TRACK_INTENSITY_DELTA_DBZ
            )
            candidates.append((score, candidate))
        if not candidates:
            continue
        reference = min(candidates, key=lambda item: item[0])[1]
        track.append(reference)
    return track


def _motion_from_frame_results(frame_results: list[AnalyzedFrame]) -> StormMotion:
    """Estimate motion/trend from a plausibly matched component track."""

    track = _tracked_core_samples(frame_results)
    if len(track) < 2:
        return StormMotion(None, None, None, None, None, None)

    latest = track[0]
    older = track[-1]
    delta_seconds = latest.frame_time - older.frame_time
    if delta_seconds <= 0:
        return StormMotion(None, None, None, None, None, None)

    elapsed_hours = delta_seconds / 3600
    moved_km = haversine_km(
        older.latitude,
        older.longitude,
        latest.latitude,
        latest.longitude,
    )
    speed_kmh = moved_km / elapsed_hours
    distance_delta = latest.distance_km - older.distance_km
    radial_closing_speed_kmh = -distance_delta / elapsed_hours
    approaching = (
        distance_delta < -0.5
        and radial_closing_speed_kmh >= MIN_APPROACHING_RADIAL_SPEED_KMH
    )
    eta_minutes = None
    if approaching:
        estimate = max(0, round((latest.distance_km / radial_closing_speed_kmh) * 60))
        if estimate <= MAX_ACTIONABLE_ETA_MINUTES:
            eta_minutes = estimate

    dbz_delta = latest.max_dbz - older.max_dbz
    return StormMotion(
        bearing=bearing_degrees(
            older.latitude,
            older.longitude,
            latest.latitude,
            latest.longitude,
        ),
        speed_kmh=round(speed_kmh, 1),
        approaching=approaching,
        eta_minutes=eta_minutes,
        dbz_trend=_trend_from_delta(dbz_delta, deadband=2, positive="rising", negative="falling"),
        distance_trend=_trend_from_delta(
            distance_delta, deadband=1, positive="receding", negative="approaching"
        ),
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
    core_watch_dbz: int = 50,
    core_warning_dbz: int = 55,
    core_urgent_dbz: int = 60,
    min_core_pixels: int = 1,
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
            core_watch_dbz=core_watch_dbz,
            core_warning_dbz=core_warning_dbz,
            core_urgent_dbz=core_urgent_dbz,
            min_core_pixels=min_core_pixels,
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

    if latest.core_urgent_distance_km is not None:
        selected_threshold = latest.selected_core_threshold_dbz
        selected_distance = latest.core_urgent_distance_km
        selected_lat = latest.core_urgent_latitude
        selected_lon = latest.core_urgent_longitude
    elif latest.core_warning_distance_km is not None:
        selected_threshold = latest.selected_core_threshold_dbz
        selected_distance = latest.core_warning_distance_km
        selected_lat = latest.core_warning_latitude
        selected_lon = latest.core_warning_longitude
    elif latest.core_watch_distance_km is not None:
        selected_threshold = latest.selected_core_threshold_dbz
        selected_distance = latest.core_watch_distance_km
        selected_lat = latest.core_watch_latitude
        selected_lon = latest.core_watch_longitude
    else:
        selected_threshold = None
        selected_distance = None
        selected_lat = None
        selected_lon = None

    frame_age_seconds = now - latest.frame_time
    if frame_age_seconds < 0:
        frame_age_seconds = 0

    motion = _motion_from_frame_results(frame_results)
    try:
        metadata_generated_time = int(metadata["generated"])
    except (KeyError, TypeError, ValueError):
        metadata_generated_time = None

    return RadarAnalysis(
        frame_time=latest.frame_time,
        frame_age_seconds=frame_age_seconds,
        max_dbz=max_dbz,
        max_core_dbz=latest.max_core_dbz,
        core50_distance_km=latest.core50_distance_km,
        core55_distance_km=latest.core55_distance_km,
        core60_distance_km=latest.core60_distance_km,
        core_watch_distance_km=latest.core_watch_distance_km,
        core_warning_distance_km=latest.core_warning_distance_km,
        core_urgent_distance_km=latest.core_urgent_distance_km,
        selected_core_threshold_dbz=selected_threshold,
        selected_core_distance_km=selected_distance,
        selected_core_latitude=selected_lat,
        selected_core_longitude=selected_lon,
        selected_core_area_km2=latest.selected_core_area_km2,
        selected_core_pixel_count=latest.selected_core_pixel_count,
        selected_core_max_dbz=latest.selected_core_max_dbz,
        storm_cores=latest.storm_cores,
        core_count=latest.core_count,
        storm_motion_bearing=motion.bearing,
        storm_motion_speed_kmh=motion.speed_kmh,
        storm_approaching=motion.approaching,
        storm_eta_minutes=motion.eta_minutes,
        dbz_trend=motion.dbz_trend,
        distance_trend=motion.distance_trend,
        frames_analyzed=len(frame_results),
        frame_host=host,
        frame_path=latest.frame_path,
        metadata_generated_time=metadata_generated_time,
        tile_size=RAINVIEWER_TILE_SIZE,
        display_zoom=min(max(0, int(zoom)), RAINVIEWER_MAX_NATIVE_ZOOM),
        max_native_zoom=RAINVIEWER_MAX_NATIVE_ZOOM,
        color_scheme_id=RAINVIEWER_COLOR_SCHEME_ID,
        tile_options=RAINVIEWER_TILE_OPTIONS,
        selected_core_centroid_latitude=latest.selected_core_centroid_latitude,
        selected_core_centroid_longitude=latest.selected_core_centroid_longitude,
        overlay_cores=latest.overlay_cores,
        overlay_selected_core_forced_included=(
            latest.overlay_selected_core_forced_included
        ),
    )
