"""Lila Framework v2.0.1 In-Memory Diagnostic & Debug Engine.
Tracks the last 100 requests in RAM (collections.deque) with zero disk I/O.
"""

import time
import os
import datetime
from collections import deque
from typing import Optional, Dict, Any, List

psutil = None
HAS_PSUTIL = False


def _get_psutil():
    """Lazy accessor so App() stays light when psutil is installed but unused."""
    global psutil, HAS_PSUTIL
    if psutil is None:
        try:
            import psutil as psutil_module

            psutil = psutil_module
            HAS_PSUTIL = True
        except ImportError:
            HAS_PSUTIL = False
    return psutil

DEBUG_HISTORY: deque = deque(maxlen=100)

IGNORE_EXTENSIONS = frozenset({
    ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2", ".ttf",
})


class DebugStore:
    """Zero-IO In-Memory request inspector for debugging and metrics."""

    @classmethod
    def record(cls, entry: Dict[str, Any]) -> None:
        DEBUG_HISTORY.appendleft(entry)

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        return list(DEBUG_HISTORY)

    @classmethod
    def clear(cls) -> None:
        DEBUG_HISTORY.clear()

    @classmethod
    def get_system_metrics(cls) -> Dict[str, Any]:
        """Returns RAM, CPU and process metrics safely without failing if psutil is absent."""
        psutil_module = _get_psutil()
        if HAS_PSUTIL and psutil_module is not None:
            try:
                proc = psutil_module.Process(os.getpid())
                mem_info = proc.memory_info()
                vmem = psutil_module.virtual_memory()
                return {
                    "process_ram_mb": round(mem_info.rss / (1024 * 1024), 2),
                    "system_ram_total_mb": round(vmem.total / (1024 * 1024), 2),
                    "system_ram_percent": vmem.percent,
                    "cpu_percent": psutil_module.cpu_percent(interval=0),
                    "threads": proc.num_threads(),
                }
            except Exception:
                pass

        return {
            "process_ram_mb": 0.0,
            "system_ram_total_mb": 0.0,
            "system_ram_percent": 0.0,
            "cpu_percent": 0.0,
            "threads": 1,
        }


class PureASGIDebugMiddleware:
    """Pure ASGI Middleware capturing timing & memory into DebugStore."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(("/_lila", "/debug", "/favicon")):
            await self.app(scope, receive, send)
            return

        if any(path.endswith(ext) for ext in IGNORE_EXTENSIONS):
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        status_code = [500]
        responded = [False]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
                responded[0] = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"

            DebugStore.record({
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "method": scope.get("method", "GET"),
                "path": path,
                "status": status_code[0],
                "duration_ms": round(elapsed_ms, 2),
                "ip": client_ip,
            })

