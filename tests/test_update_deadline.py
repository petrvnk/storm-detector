"""Update deadline and cancellation-drain behavior tests."""

from __future__ import annotations

import asyncio
import importlib.util
import threading
from types import SimpleNamespace

import custom_components.radar_hail_risk.coordinator as coordinator_module
import custom_components.radar_hail_risk.rainviewer as rainviewer_module
import pytest
from custom_components.radar_hail_risk.const import (
    ATTR_DEGRADATION_REASONS,
    ATTR_RAINVIEWER_DIAGNOSTICS,
    ATTR_SOURCE_STATUS,
    DOMAIN,
)
from custom_components.radar_hail_risk.coordinator import RadarHailRiskCoordinator
from custom_components.radar_hail_risk.rainviewer import (
    MAX_PARALLEL_TILE_FETCHES,
    analyze_single_radar_frame,
    global_px_to_latlon,
)

HA_TESTING_AVAILABLE = (
    importlib.util.find_spec("pytest_homeassistant_custom_component") is not None
)


async def test_analysis_deadline_cancels_and_drains_task() -> None:
    analysis_started = asyncio.Event()
    analysis_cancelled = asyncio.Event()

    async def blocked_analysis() -> None:
        analysis_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            analysis_cancelled.set()

    analysis_task = asyncio.create_task(blocked_analysis())
    await analysis_started.wait()

    with pytest.raises(asyncio.TimeoutError):
        await coordinator_module._await_task_with_deadline(analysis_task, timeout=0)

    assert analysis_task.done()
    assert analysis_cancelled.is_set()


async def test_cancelling_deadline_wrapper_during_timeout_drain_waits_for_worker() -> None:
    loop = asyncio.get_running_loop()
    worker_started = asyncio.Event()
    timeout_cleanup_started = asyncio.Event()
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

    class ObservedTask(asyncio.Task):
        def cancel(self, msg: object | None = None) -> bool:
            timeout_cleanup_started.set()
            return super().cancel(msg)

    analysis_task = ObservedTask(
        rainviewer_module._run_in_executor_and_drain(blocked_worker),
        loop=loop,
    )
    await worker_started.wait()
    deadline_task = asyncio.create_task(
        coordinator_module._await_task_with_deadline(analysis_task, timeout=0)
    )
    await timeout_cleanup_started.wait()

    assert deadline_task.done() is False
    assert analysis_task.done() is False
    assert active_workers == 1

    deadline_task.cancel()
    try:
        await asyncio.sleep(0)
        assert deadline_task.done() is False
        assert analysis_task.done() is False
        assert active_workers == 1
    finally:
        release_worker.set()

    with pytest.raises(asyncio.CancelledError):
        await deadline_task
    assert analysis_task.done()
    assert active_workers == 0


@pytest.mark.skipif(
    not HA_TESTING_AVAILABLE,
    reason="Home Assistant test support is unavailable on this Python version",
)
async def test_frame_analysis_deadline_cancels_and_publishes_timeout_diagnostic(
    hass,
    monkeypatch,
) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    analysis_started = asyncio.Event()
    analysis_cancelled = asyncio.Event()
    observed_timeouts: list[float] = []

    async def fake_metadata(_session: object) -> dict[str, object]:
        return {
            "radar": {"past": [{"time": 1_710_000_000, "path": "/frame"}]},
            "host": "https://tilecache.rainviewer.com",
        }

    async def fake_colors(_session: object) -> dict[tuple[int, int, int, int], int]:
        return {(255, 255, 255, 255): 0}

    async def blocked_analysis(*_args: object, **_kwargs: object) -> None:
        analysis_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            analysis_cancelled.set()

    real_wait_for = asyncio.wait_for

    async def expire_after_start(awaitable, timeout: float):
        observed_timeouts.append(timeout)
        task = asyncio.ensure_future(awaitable)
        await analysis_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        raise asyncio.TimeoutError

    monkeypatch.setattr(coordinator_module, "fetch_radar_metadata", fake_metadata)
    monkeypatch.setattr(coordinator_module, "fetch_rainviewer_color_lookup", fake_colors)
    monkeypatch.setattr(coordinator_module, "analyze_recent_frames", blocked_analysis)
    monkeypatch.setattr(coordinator_module.asyncio, "wait_for", expire_after_start)

    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    coordinator = RadarHailRiskCoordinator(hass, None, "Radar Hail Risk", entry)
    payload = await coordinator._async_update_data()

    assert observed_timeouts == [coordinator_module.RADAR_ANALYSIS_DEADLINE_SECONDS]
    assert analysis_cancelled.is_set()
    assert payload[ATTR_SOURCE_STATUS]["radar"] == "degraded"
    assert "radar_analysis_timeout" in payload[ATTR_RAINVIEWER_DIAGNOSTICS]
    assert "radar_analysis_timeout" in payload[ATTR_DEGRADATION_REASONS]
    assert "radar_analysis_error" not in payload[ATTR_RAINVIEWER_DIAGNOSTICS]
    assert real_wait_for is not expire_after_start


async def test_cancelling_frame_analysis_drains_inflight_and_queued_tile_tasks(
    monkeypatch,
) -> None:
    fetch_started = asyncio.Event()
    release_fetches = asyncio.Event()
    started = 0
    cancelled = 0
    active = 0

    async def blocked_fetch(*_args: object, **_kwargs: object) -> bytes:
        nonlocal active, cancelled, started
        started += 1
        active += 1
        if active == MAX_PARALLEL_TILE_FETCHES:
            fetch_started.set()
        try:
            await release_fetches.wait()
            return b"image"
        except asyncio.CancelledError:
            cancelled += 1
            await asyncio.sleep(0)
            raise
        finally:
            active -= 1

    monkeypatch.setattr(rainviewer_module, "_fetch_tile_bytes", blocked_fetch)

    zoom = 7
    center_lat, center_lon = global_px_to_latlon(20 * 512 + 256, 20 * 512 + 256, zoom)
    analysis_task = asyncio.create_task(
        analyze_single_radar_frame(
            SimpleNamespace(),
            "https://tilecache.rainviewer.com",
            {"time": 123, "path": "/cancel"},
            center_lat,
            center_lon,
            analysis_radius_km=20,
            zoom=zoom,
            color_lookup={(255, 0, 0, 255): 60},
        )
    )

    await fetch_started.wait()
    analysis_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await analysis_task

    await asyncio.sleep(0)
    assert started == MAX_PARALLEL_TILE_FETCHES
    assert cancelled == MAX_PARALLEL_TILE_FETCHES
    assert active == 0
