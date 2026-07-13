from starlette.background import BackgroundTask as StarletteBackgroundTask
import pickle
from lila.core.cache import _REDIS_CLIENT


class BackgroundTask:
    """
    English: Custom BackgroundTask that routes tasks to Redis if available, or falls back to in-memory execution.
    """
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._starlette_task = None

        if _REDIS_CLIENT is not None:
            try:
                func_path = f"{func.__module__}:{func.__qualname__}"
                payload = {
                    "func_path": func_path,
                    "args": args,
                    "kwargs": kwargs
                }
                _REDIS_CLIENT.lpush("lila:tasks", pickle.dumps(payload))
            except Exception:
                self._starlette_task = StarletteBackgroundTask(func, *args, **kwargs)
        else:
            self._starlette_task = StarletteBackgroundTask(func, *args, **kwargs)

    async def __call__(self) -> None:
        if self._starlette_task is not None:
            await self._starlette_task()