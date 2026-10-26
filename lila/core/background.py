"""Lila Framework v2.0.0 Background Tasks.
Routes tasks to Redis queue if Redis is configured, or executes via Starlette BackgroundTasks.
"""

import pickle
from starlette.background import BackgroundTask as StarletteBackgroundTask
from starlette.background import BackgroundTasks
from lila.core.cache import Cache


class BackgroundTask:
    """Dispatches background work to Redis worker or Starlette execution."""

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._starlette_task = None

        if Cache._get_driver() == "redis":
            client = Cache._get_redis_sync()
            if client is not None:
                try:
                    func_path = f"{func.__module__}:{func.__qualname__}"
                    payload = {
                        "func_path": func_path,
                        "args": args,
                        "kwargs": kwargs,
                    }
                    client.lpush("lila:tasks", pickle.dumps(payload))
                    return
                except Exception:
                    pass

        self._starlette_task = StarletteBackgroundTask(func, *args, **kwargs)

    async def __call__(self) -> None:
        if self._starlette_task is not None:
            await self._starlette_task()
