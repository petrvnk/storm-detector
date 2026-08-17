"""Async cancellation helpers shared by the integration runtime."""

from __future__ import annotations

import asyncio
from typing import Any


async def drain_future(future: asyncio.Future[Any]) -> None:
    """Wait for a future through repeated cancellation of the current task."""

    while True:
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            if future.done():
                return
        except BaseException:
            return
        else:
            return
