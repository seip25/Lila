from starlette.background import BackgroundTask as StarletteBackgroundTask
import pickle
from lila.core.cache import _get_redis_client


class BackgroundTask:
    """Custom BackgroundTask that routes tasks to Redis if available, or falls back to in-memory execution."""

    def __init__(self, func, *args, **kwargs):
        """Initialize background task and route to Redis queue if online, otherwise fallback to Starlette."""
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._starlette_task = None

        client = _get_redis_client()
        if client is not None:
            try:
                func_path = f"{func.__module__}:{func.__qualname__}"
                payload = {
                    "func_path": func_path,
                    "args": args,
                    "kwargs": kwargs
                }
                client.lpush("lila:tasks", pickle.dumps(payload))
            except Exception:
                self._starlette_task = StarletteBackgroundTask(func, *args, **kwargs)
        else:
            self._starlette_task = StarletteBackgroundTask(func, *args, **kwargs)

    async def __call__(self) -> None:
        """Execute the task if falling back to Starlette background execution."""
        if self._starlette_task is not None:
            await self._starlette_task()