"""Home Assistant runtime and performance hardening tests."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import patch

import custom_components.storm_detector.rainviewer as rainviewer_module
import pytest
from custom_components.storm_detector import async_unload_entry
from custom_components.storm_detector.const import (
    CONF_ANALYSIS_RADIUS_KM,
    CONF_RAINVIEWER_FRAMES,
    CONF_RAINVIEWER_ZOOM,
    DEFAULT_ANALYSIS_RADIUS_KM,
    DEFAULT_RAINVIEWER_FRAMES,
    DEFAULT_RAINVIEWER_ZOOM,
    DOMAIN,
    PARAMETER_SPECS,
)
from custom_components.storm_detector.rainviewer import (
    MAX_PARALLEL_TILE_FETCHES,
    analyze_recent_frames,
    analyze_single_radar_frame,
    global_px_to_latlon,
)


class FakeEntry:
    entry_id = "entry-runtime"
    data = {}
    options = {}


async def test_tile_fetching_is_parallel_with_a_bounded_concurrency() -> None:
    concurrency_reached = asyncio.Event()
    release_requests = asyncio.Event()

    class Response:
        status = 200

        async def read(self) -> bytes:
            return b"not-an-image"

        def release(self) -> None:
            return None

    class TrackingSession:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0

        async def get(self, _url: str, timeout: int = 20) -> Response:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if self.active == MAX_PARALLEL_TILE_FETCHES:
                concurrency_reached.set()
            try:
                await release_requests.wait()
                return Response()
            finally:
                self.active -= 1

    zoom = 7
    center_lat, center_lon = global_px_to_latlon(20 * 512 + 256, 20 * 512 + 256, zoom)
    session = TrackingSession()

    analysis_task = asyncio.create_task(
        analyze_single_radar_frame(
            session,
            "https://tilecache.rainviewer.com",
            {"time": 123, "path": "/parallel"},
            center_lat,
            center_lon,
            analysis_radius_km=20,
            zoom=zoom,
            color_lookup={(255, 0, 0, 255): 60},
        )
    )
    await concurrency_reached.wait()
    release_requests.set()
    result = await analysis_task

    assert result is None
    assert session.max_active == MAX_PARALLEL_TILE_FETCHES


@pytest.mark.parametrize(
    ("analysis_radius_km", "zoom", "frame_count", "tiles_per_frame", "total_tiles"),
    (
        (
            DEFAULT_ANALYSIS_RADIUS_KM,
            DEFAULT_RAINVIEWER_ZOOM,
            DEFAULT_RAINVIEWER_FRAMES,
            9,
            9 * DEFAULT_RAINVIEWER_FRAMES,
        ),
        (
            PARAMETER_SPECS[CONF_ANALYSIS_RADIUS_KM]["max"],
            PARAMETER_SPECS[CONF_RAINVIEWER_ZOOM]["max"],
            PARAMETER_SPECS[CONF_RAINVIEWER_FRAMES]["max"],
            25,
            25 * PARAMETER_SPECS[CONF_RAINVIEWER_FRAMES]["max"],
        ),
    ),
)
async def test_default_and_max_configured_workloads_are_bounded_and_responsive(
    analysis_radius_km: float,
    zoom: int,
    frame_count: int,
    tiles_per_frame: int,
    total_tiles: int,
) -> None:
    tile_requests = 0
    active_requests = 0
    max_active_requests = 0
    concurrency_reached = asyncio.Event()
    release_requests = asyncio.Event()

    async def empty_tile(*_args: object, **_kwargs: object) -> None:
        nonlocal active_requests, max_active_requests, tile_requests
        tile_requests += 1
        active_requests += 1
        max_active_requests = max(max_active_requests, active_requests)
        if active_requests == MAX_PARALLEL_TILE_FETCHES:
            concurrency_reached.set()
        try:
            await release_requests.wait()
            return None
        finally:
            active_requests -= 1

    equator_tile_y = 2 ** (zoom - 1)
    center_lat, center_lon = global_px_to_latlon(
        20 * 512 + 256,
        equator_tile_y * 512 + 256,
        zoom,
    )
    metadata = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [
                {"time": 1_710_000_000 - index, "path": f"/workload-{index}"}
                for index in range(frame_count)
            ]
        },
    }
    with patch(
        "custom_components.storm_detector.rainviewer._fetch_tile_bytes",
        empty_tile,
    ):
        analysis_task = asyncio.create_task(
            analyze_recent_frames(
                SimpleNamespace(),
                metadata,
                center_lat,
                center_lon,
                analysis_radius_km=analysis_radius_km,
                required_frames=frame_count,
                zoom=zoom,
                color_lookup={(255, 0, 0, 255): 60},
            )
        )
        await concurrency_reached.wait()
        responsive = asyncio.Event()
        asyncio.get_running_loop().call_soon(responsive.set)
        await responsive.wait()

        assert analysis_task.done() is False
        assert max_active_requests == MAX_PARALLEL_TILE_FETCHES
        release_requests.set()
        result = await analysis_task

    assert frame_count in {
        DEFAULT_RAINVIEWER_FRAMES,
        PARAMETER_SPECS[CONF_RAINVIEWER_FRAMES]["max"],
    }
    assert total_tiles == tiles_per_frame * frame_count
    assert result is None
    assert tile_requests == total_tiles
    assert active_requests == 0


async def test_image_decode_and_core_analysis_run_off_the_event_loop() -> None:
    loop = asyncio.get_running_loop()
    event_loop_thread = threading.get_ident()
    decode_started = asyncio.Event()
    release_decode = threading.Event()
    decode_threads: list[int] = []
    analysis_threads: list[int] = []
    expected = SimpleNamespace(analyzed_pixels=1)

    async def fake_fetch(*_args: object, **_kwargs: object) -> bytes:
        return b"image"

    def fake_decode(*_args: object, **_kwargs: object) -> list[list[int | None]]:
        decode_threads.append(threading.get_ident())
        loop.call_soon_threadsafe(decode_started.set)
        release_decode.wait()
        return [[60]]

    def fake_analyze(*_args: object, **_kwargs: object) -> SimpleNamespace:
        analysis_threads.append(threading.get_ident())
        return expected

    zoom = 7
    center_lat, center_lon = global_px_to_latlon(20 * 512, 20 * 512, zoom)
    with patch(
        "custom_components.storm_detector.rainviewer._fetch_tile_bytes",
        fake_fetch,
    ), patch(
        "custom_components.storm_detector.rainviewer._decode_dbz_grid",
        fake_decode,
    ), patch(
        "custom_components.storm_detector.rainviewer._analyse_dbz_grid",
        fake_analyze,
    ):
        analysis_task = asyncio.create_task(
            analyze_single_radar_frame(
                SimpleNamespace(),
                "https://tilecache.rainviewer.com",
                {"time": 123, "path": "/executor"},
                center_lat,
                center_lon,
                analysis_radius_km=20,
                zoom=zoom,
                color_lookup={(255, 0, 0, 255): 60},
            )
        )
        await decode_started.wait()
        await asyncio.sleep(0)
        assert analysis_task.done() is False
        release_decode.set()
        result = await analysis_task

    assert result is expected
    assert decode_threads
    assert all(thread_id != event_loop_thread for thread_id in decode_threads)
    assert analysis_threads
    assert all(thread_id != event_loop_thread for thread_id in analysis_threads)


async def test_cancelling_frame_analysis_waits_for_inflight_decode_workers(
    monkeypatch,
) -> None:
    loop = asyncio.get_running_loop()
    workers_started = asyncio.Event()
    release_workers = threading.Event()
    worker_lock = threading.Lock()
    active_workers = 0

    async def fake_fetch(*_args: object, **_kwargs: object) -> bytes:
        return b"image"

    def blocked_tile_points(*_args: object, **_kwargs: object) -> dict[object, object]:
        nonlocal active_workers
        with worker_lock:
            active_workers += 1
            if active_workers == MAX_PARALLEL_TILE_FETCHES:
                loop.call_soon_threadsafe(workers_started.set)
        try:
            release_workers.wait()
            return {}
        finally:
            with worker_lock:
                active_workers -= 1

    monkeypatch.setattr(rainviewer_module, "_fetch_tile_bytes", fake_fetch)
    monkeypatch.setattr(rainviewer_module, "_tile_points_from_bytes", blocked_tile_points)

    zoom = 7
    center_lat, center_lon = global_px_to_latlon(20 * 512 + 256, 20 * 512 + 256, zoom)
    analysis_task = asyncio.create_task(
        analyze_single_radar_frame(
            SimpleNamespace(),
            "https://tilecache.rainviewer.com",
            {"time": 123, "path": "/cancel-decode"},
            center_lat,
            center_lon,
            analysis_radius_km=20,
            zoom=zoom,
            color_lookup={(255, 0, 0, 255): 60},
        )
    )

    await workers_started.wait()
    analysis_task.cancel()
    try:
        await asyncio.sleep(0)
        assert analysis_task.done() is False
        assert active_workers == MAX_PARALLEL_TILE_FETCHES

        analysis_task.cancel()
        await asyncio.sleep(0)
        assert analysis_task.done() is False
        assert active_workers == MAX_PARALLEL_TILE_FETCHES
    finally:
        release_workers.set()

    with pytest.raises(asyncio.CancelledError):
        await analysis_task
    assert active_workers == 0


async def test_executor_drain_survives_repeated_cancellation() -> None:
    loop = asyncio.get_running_loop()
    worker_started = asyncio.Event()
    release_worker = threading.Event()
    active_workers = 0

    def blocked_worker() -> None:
        nonlocal active_workers
        active_workers += 1
        loop.call_soon_threadsafe(worker_started.set)
        try:
            release_worker.wait()
        finally:
            active_workers -= 1

    task = asyncio.create_task(
        rainviewer_module._run_in_executor_and_drain(blocked_worker)
    )
    await worker_started.wait()

    task.cancel()
    await asyncio.sleep(0)
    assert task.done() is False
    assert active_workers == 1

    task.cancel()
    try:
        await asyncio.sleep(0)
        assert task.done() is False
        assert active_workers == 1
    finally:
        release_worker.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert active_workers == 0


async def test_cancelling_frame_analysis_waits_for_component_analysis_worker(
    monkeypatch,
) -> None:
    loop = asyncio.get_running_loop()
    worker_started = asyncio.Event()
    release_worker = threading.Event()
    active_workers = 0

    async def fake_fetch(*_args: object, **_kwargs: object) -> bytes:
        return b"image"

    def fake_tile_points(
        *_args: object, **_kwargs: object
    ) -> dict[tuple[int, int], tuple[int, float, float, float]]:
        return {(0, 0): (60, 0.0, 0.0, 0.0)}

    def blocked_analysis(*_args: object, **_kwargs: object) -> None:
        nonlocal active_workers
        active_workers += 1
        loop.call_soon_threadsafe(worker_started.set)
        try:
            release_worker.wait()
        finally:
            active_workers -= 1

    monkeypatch.setattr(rainviewer_module, "_fetch_tile_bytes", fake_fetch)
    monkeypatch.setattr(rainviewer_module, "_tile_points_from_bytes", fake_tile_points)
    monkeypatch.setattr(rainviewer_module, "_analyse_dbz_grid", blocked_analysis)

    zoom = 7
    center_lat, center_lon = global_px_to_latlon(20 * 512 + 256, 20 * 512 + 256, zoom)
    analysis_task = asyncio.create_task(
        analyze_single_radar_frame(
            SimpleNamespace(),
            "https://tilecache.rainviewer.com",
            {"time": 123, "path": "/cancel-components"},
            center_lat,
            center_lon,
            analysis_radius_km=20,
            zoom=zoom,
            color_lookup={(255, 0, 0, 255): 60},
        )
    )

    await worker_started.wait()
    analysis_task.cancel()
    try:
        await asyncio.sleep(0)
        assert analysis_task.done() is False
        assert active_workers == 1

        analysis_task.cancel()
        await asyncio.sleep(0)
        assert analysis_task.done() is False
        assert active_workers == 1
    finally:
        release_worker.set()

    with pytest.raises(asyncio.CancelledError):
        await analysis_task
    assert active_workers == 0


async def test_failed_platform_unload_preserves_entry_runtime_state() -> None:
    entry = FakeEntry()
    runtime_state = {"coordinator": object()}

    async def fail_unload(*_args: object, **_kwargs: object) -> bool:
        return False

    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "frontend_static_registered": True,
                entry.entry_id: runtime_state,
            }
        },
        config_entries=SimpleNamespace(async_unload_platforms=fail_unload),
    )

    result = await async_unload_entry(hass, entry)

    assert result is False
    assert hass.data[DOMAIN][entry.entry_id] is runtime_state


async def test_successful_platform_unload_removes_only_entry_runtime_state() -> None:
    entry = FakeEntry()

    async def unload(*_args: object, **_kwargs: object) -> bool:
        return True

    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "frontend_static_registered": True,
                entry.entry_id: {"coordinator": object()},
            }
        },
        config_entries=SimpleNamespace(async_unload_platforms=unload),
    )

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]
    assert hass.data[DOMAIN]["frontend_static_registered"] is True
