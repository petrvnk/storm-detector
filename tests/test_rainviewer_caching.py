from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import custom_components.storm_detector.rainviewer as rainviewer
import pytest
from custom_components.storm_detector.rainviewer import AnalyzedFrame


def _analysis_args(
    frame_time: int,
    *,
    latitude: float = 49.9,
    watch_dbz: int = 50,
    color_lookup: dict[tuple[int, int, int, int], int] | None = None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    lookup = color_lookup if color_lookup is not None else {(255, 0, 0, 255): 60}
    return (
        (
            object(),
            "https://tilecache.rainviewer.com",
            {"time": frame_time, "path": f"/v2/radar/{frame_time}"},
            latitude,
            18.1,
            80.0,
            7,
            lookup,
        ),
        {
            "core_watch_dbz": watch_dbz,
            "core_warning_dbz": 55,
            "core_urgent_dbz": 60,
            "min_core_pixels": 3,
        },
    )


@pytest.mark.asyncio
async def test_frame_cache_reuses_unchanged_window_and_only_analyzes_new_frame() -> None:
    sentinel = cast(AnalyzedFrame, object())
    lookup = {(255, 0, 0, 255): 60}
    analyzer = AsyncMock(return_value=sentinel)

    with patch.object(rainviewer, "analyze_single_radar_frame", analyzer):
        for frame_time in (400, 300, 200, 100):
            args, kwargs = _analysis_args(frame_time, color_lookup=lookup)
            assert await rainviewer._analyze_frame_cached(*args, **kwargs) is sentinel
        for frame_time in (500, 400, 300, 200):
            args, kwargs = _analysis_args(frame_time, color_lookup=lookup)
            assert await rainviewer._analyze_frame_cached(*args, **kwargs) is sentinel

    assert analyzer.await_count == 5
    assert len(rainviewer._ANALYZED_FRAME_CACHE) == 5


@pytest.mark.asyncio
async def test_frame_cache_invalidates_for_location_threshold_and_color_table() -> None:
    sentinel = cast(AnalyzedFrame, object())
    analyzer = AsyncMock(return_value=sentinel)
    first_lookup = {(255, 0, 0, 255): 60}
    second_lookup = {(255, 0, 0, 255): 59}

    with patch.object(rainviewer, "analyze_single_radar_frame", analyzer):
        args, kwargs = _analysis_args(100, color_lookup=first_lookup)
        await rainviewer._analyze_frame_cached(*args, **kwargs)
        args, kwargs = _analysis_args(100, latitude=49.91, color_lookup=first_lookup)
        await rainviewer._analyze_frame_cached(*args, **kwargs)
        args, kwargs = _analysis_args(100, watch_dbz=48, color_lookup=first_lookup)
        await rainviewer._analyze_frame_cached(*args, **kwargs)
        args, kwargs = _analysis_args(100, color_lookup=second_lookup)
        await rainviewer._analyze_frame_cached(*args, **kwargs)

    assert analyzer.await_count == 4


@pytest.mark.asyncio
async def test_frame_cache_is_bounded_lru_and_does_not_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = cast(AnalyzedFrame, object())
    lookup = {(255, 0, 0, 255): 60}
    analyzer = AsyncMock(side_effect=[sentinel, sentinel, sentinel, sentinel, None, sentinel])
    monkeypatch.setattr(rainviewer, "ANALYZED_FRAME_CACHE_MAX_ENTRIES", 2)

    with patch.object(rainviewer, "analyze_single_radar_frame", analyzer):
        for frame_time in (100, 200, 300, 100):
            args, kwargs = _analysis_args(frame_time, color_lookup=lookup)
            await rainviewer._analyze_frame_cached(*args, **kwargs)
        args, kwargs = _analysis_args(400, color_lookup=lookup)
        assert await rainviewer._analyze_frame_cached(*args, **kwargs) is None
        assert await rainviewer._analyze_frame_cached(*args, **kwargs) is sentinel

    assert analyzer.await_count == 6
    assert len(rainviewer._ANALYZED_FRAME_CACHE) == 2


@pytest.mark.asyncio
async def test_frame_cache_deduplicates_concurrent_analysis() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    sentinel = cast(AnalyzedFrame, object())

    async def analyze(*_args: Any, **_kwargs: Any) -> AnalyzedFrame:
        started.set()
        await release.wait()
        return sentinel

    args, kwargs = _analysis_args(100)
    with patch.object(rainviewer, "analyze_single_radar_frame", analyze):
        first = asyncio.create_task(rainviewer._analyze_frame_cached(*args, **kwargs))
        await started.wait()
        second = asyncio.create_task(rainviewer._analyze_frame_cached(*args, **kwargs))
        await asyncio.sleep(0)
        assert len(rainviewer._ANALYZED_FRAME_INFLIGHT) == 1
        release.set()
        assert await first is sentinel
        assert await second is sentinel

    assert not rainviewer._ANALYZED_FRAME_INFLIGHT
    assert len(rainviewer._ANALYZED_FRAME_CACHE) == 1


@pytest.mark.asyncio
async def test_cancelled_only_waiter_returns_promptly_and_cancels_shared_work() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def analyze(*_args: Any, **_kwargs: Any) -> AnalyzedFrame:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        raise AssertionError("unreachable")

    args, kwargs = _analysis_args(100)
    with patch.object(rainviewer, "analyze_single_radar_frame", analyze):
        task = asyncio.create_task(rainviewer._analyze_frame_cached(*args, **kwargs))
        await started.wait()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=0.01)
        await asyncio.wait_for(cancelled.wait(), timeout=0.1)
        await asyncio.sleep(0)

    assert not rainviewer._ANALYZED_FRAME_INFLIGHT
    assert not rainviewer._ANALYZED_FRAME_CACHE


@pytest.mark.asyncio
async def test_cancelling_one_waiter_keeps_shared_work_for_other_waiter() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    sentinel = cast(AnalyzedFrame, object())

    async def analyze(*_args: Any, **_kwargs: Any) -> AnalyzedFrame:
        started.set()
        await release.wait()
        return sentinel

    args, kwargs = _analysis_args(100)
    with patch.object(rainviewer, "analyze_single_radar_frame", analyze):
        first = asyncio.create_task(rainviewer._analyze_frame_cached(*args, **kwargs))
        await started.wait()
        second = asyncio.create_task(rainviewer._analyze_frame_cached(*args, **kwargs))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        assert await second is sentinel

    assert not rainviewer._ANALYZED_FRAME_INFLIGHT
    assert len(rainviewer._ANALYZED_FRAME_CACHE) == 1


class FakeResponse:
    def __init__(
        self,
        status: int,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._payload = payload or {}
        self.headers = headers or {}
        self.closed = False

    async def json(self, **_kwargs: Any) -> dict[str, Any]:
        return self._payload

    async def close(self) -> None:
        self.closed = True


class SequenceSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls = 0

    async def get(self, _url: str, *, timeout: int) -> FakeResponse:
        del timeout
        self.calls += 1
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_429_honors_retry_after_blocks_origin_and_recovers() -> None:
    url = "https://api.rainviewer.com/public/weather-maps.json"
    session = SequenceSession(
        [
            FakeResponse(429, headers={"Retry-After": "120"}),
            FakeResponse(200, payload={"radar": {"past": []}}),
        ]
    )

    with patch.object(rainviewer.random, "uniform", return_value=1.0):
        assert await rainviewer._safe_get_json(session, url) is None
    assert session.calls == 1
    assert rainviewer._request_backoff_remaining(url) >= 119
    assert await rainviewer._safe_get_json(session, url) is None
    assert session.calls == 1

    origin = rainviewer._request_origin(url)
    state = rainviewer._REQUEST_BACKOFF[origin]
    rainviewer._REQUEST_BACKOFF[origin] = replace(state, blocked_until=0.0)
    assert await rainviewer._safe_get_json(session, url) == {"radar": {"past": []}}
    assert session.calls == 2
    assert origin not in rainviewer._REQUEST_BACKOFF


@pytest.mark.asyncio
async def test_5xx_retries_once_then_cools_exact_url_and_recovers() -> None:
    url = "https://api.rainviewer.com/public/weather-maps.json"
    session = SequenceSession(
        [
            FakeResponse(503),
            FakeResponse(503),
            FakeResponse(200, payload={"ok": True}),
        ]
    )

    with patch.object(rainviewer.random, "uniform", return_value=1.0):
        assert (
            await rainviewer._safe_get_json(
                session,
                url,
                retry_attempts=1,
                retry_backoff_seconds=0,
            )
            is None
        )
    assert session.calls == 2
    assert url in rainviewer._REQUEST_BACKOFF
    assert await rainviewer._safe_get_json(session, url) is None
    assert session.calls == 2

    state = rainviewer._REQUEST_BACKOFF[url]
    rainviewer._REQUEST_BACKOFF[url] = replace(state, blocked_until=0.0)
    assert await rainviewer._safe_get_json(session, url) == {"ok": True}
    assert session.calls == 3
    assert url not in rainviewer._REQUEST_BACKOFF


@pytest.mark.asyncio
async def test_metadata_returns_last_success_during_transient_outage() -> None:
    payload = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {"past": [{"time": 100, "path": "/v2/radar/100"}]},
    }
    fetch = AsyncMock(side_effect=[payload, None, None])

    with patch.object(rainviewer, "_safe_get_json", fetch):
        assert (
            await rainviewer.fetch_radar_metadata(
                object(), api_base="https://api.example", ttl_seconds=0
            )
            == payload
        )
        assert (
            await rainviewer.fetch_radar_metadata(
                object(), api_base="https://api.example", ttl_seconds=0
            )
            == payload
        )

    assert fetch.await_count == 3


@pytest.mark.asyncio
async def test_color_table_returns_last_success_during_transient_outage() -> None:
    color_url = "https://example.test/colors.csv"
    valid = "dBZ,Universal Blue\n50,FF0000FF\n"
    fetch = AsyncMock(side_effect=[valid, None])

    with patch.object(rainviewer, "_safe_get_text", fetch):
        first = await rainviewer.fetch_rainviewer_color_lookup(
            object(), color_url=color_url, ttl_seconds=0
        )
        second = await rainviewer.fetch_rainviewer_color_lookup(
            object(), color_url=color_url, ttl_seconds=0
        )

    assert first == {(255, 0, 0, 255): 50}
    assert second == first
    assert fetch.await_count == 2


def test_retry_delay_is_exponential_and_bounded_by_jitter() -> None:
    with patch.object(rainviewer.random, "uniform", return_value=0.8):
        assert rainviewer._retry_delay(1.0, 0) == pytest.approx(0.8)
    with patch.object(rainviewer.random, "uniform", return_value=1.2):
        assert rainviewer._retry_delay(1.0, 2) == pytest.approx(4.8)
