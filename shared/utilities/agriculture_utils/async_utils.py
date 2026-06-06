# shared/utilities/agriculture_utils/async_utils.py
"""Async helpers shared across all services."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable


async def run_sync(fn: Callable, *args: Any) -> Any:
    """
    Run a blocking (CPU-bound or sync I/O) function in the default thread pool
    without blocking the event loop.

    Usage:
        from agriculture_utils.async_utils import run_sync
        image = await run_sync(Image.open, path)
        result = await run_sync(cv2.imread, str(path))
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


def utc_now() -> datetime:
    """
    Return the current UTC datetime with timezone info.

    Replaces all deprecated ``datetime.utcnow()`` calls throughout the codebase.
    ``datetime.utcnow()`` returns a naive datetime; this returns an aware one.

    Usage:
        from agriculture_utils.async_utils import utc_now
        created_at = utc_now()
    """
    return datetime.now(timezone.utc)
