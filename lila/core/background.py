"""Lila Framework v2.0.x Background Tasks.

Queues JSON tasks in Redis when available; otherwise falls back to Starlette's
in-process BackgroundTask. No pickle is used.
"""

from typing import Any

from starlette.background import BackgroundTask as StarletteBackgroundTask
from starlette.background import BackgroundTasks

from lila.core.cache import Cache
from lila.core.logger import Logger
from lila.core.responses import orjson_dumps

QUEUE_KEY = "lila:tasks"


class BackgroundTask:
    """Dispatches background work to a Redis worker or Starlette execution."""

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._starlette_task = None

        if Cache._get_driver() == "redis":
            client = Cache.redis_client()
            if client is not None:
                try:
                    payload = {
                        "func_path": f"{func.__module__}:{func.__qualname__}",
                        "args": list(args),
                        "kwargs": kwargs,
                    }
                    client.lpush(QUEUE_KEY, orjson_dumps(payload))
                    return
                except Exception as exc:
                    Logger.warning(f"[Lila Background] Could not enqueue task in Redis: {exc}")

        self._starlette_task = StarletteBackgroundTask(func, *args, **kwargs)

    async def __call__(self) -> None:
        if self._starlette_task is not None:
            await self._starlette_task()
