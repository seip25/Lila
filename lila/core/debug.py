"""Lila Framework v2.0.2 In-Memory Diagnostic & Debug Engine.
Tracks the last 100 requests in RAM (collections.deque) with zero disk I/O.
Provides unified zero-dependency telemetry with native OS fallbacks.
"""

import os
import sys
import time
import datetime
import threading
from collections import deque
from typing import Optional, Dict, Any, List, Tuple

psutil = None
HAS_PSUTIL = False
_PSUTIL_PROC = None

try:
    import psutil as _psutil
    psutil = _psutil
    HAS_PSUTIL = True
    try:
        _PSUTIL_PROC = psutil.Process(os.getpid())
        # Prime the CPU calculation so subsequent calls don't return 0.0
        _PSUTIL_PROC.cpu_percent(None)
    except Exception:
        _PSUTIL_PROC = None
except ImportError:
    psutil = None
    HAS_PSUTIL = False
    _PSUTIL_PROC = None


# Metric cache state (1.0 second in-memory cache)
_LAST_METRICS: Optional[Dict[str, Any]] = None
_LAST_METRICS_TIME: float = 0.0
_LAST_CPU_TIMES: Dict[str, float] = {
    "process_time": time.process_time(),
    "monotonic": time.monotonic(),
}


def _get_fallback_process_ram_mb() -> float:
    """Zero-dependency native fallback to measure current process RSS in MB."""
    # 1. Linux / Android
    if sys.platform.startswith("linux") or os.path.exists("/proc/self/status"):
        try:
            with open("/proc/self/status", "r", encoding="ascii") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return round(float(parts[1]) / 1024.0, 1)
        except Exception:
            pass

    # 2. Windows
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = _PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            handle = k32.GetCurrentProcess()

            func = getattr(k32, "K32GetProcessMemoryInfo", None) or getattr(ctypes.windll.psapi, "GetProcessMemoryInfo", None)
            if func:
                func.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
                func.restype = wintypes.BOOL
                if func(handle, ctypes.byref(pmc), pmc.cb):
                    return round(pmc.WorkingSetSize / (1024.0 * 1024.0), 1)
        except Exception:
            pass

    # 3. macOS / BSD / Unix
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        # On macOS ru_maxrss is in bytes; on Linux/BSD it is in kilobytes.
        if sys.platform == "darwin":
            return round(ru.ru_maxrss / (1024.0 * 1024.0), 1)
        return round(ru.ru_maxrss / 1024.0, 1)
    except Exception:
        pass

    return 0.0


def _get_fallback_system_ram() -> Tuple[float, float, float]:
    """Returns (used_mb, total_mb, percent) for system RAM without psutil."""
    # 1. Linux
    if sys.platform.startswith("linux") or os.path.exists("/proc/meminfo"):
        try:
            mem_total_kb = None
            mem_avail_kb = None
            with open("/proc/meminfo", "r", encoding="ascii") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        mem_total_kb = float(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail_kb = float(line.split()[1])
            if mem_total_kb is not None:
                total_mb = round(mem_total_kb / 1024.0, 1)
                avail_mb = round((mem_avail_kb if mem_avail_kb is not None else 0.0) / 1024.0, 1)
                used_mb = round(total_mb - avail_mb, 1)
                pct = round((used_mb / total_mb) * 100.0, 1) if total_mb > 0 else 0.0
                return used_mb, total_mb, pct
        except Exception:
            pass

    # 2. Windows
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            k32 = ctypes.windll.kernel32
            k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
            k32.GlobalMemoryStatusEx.restype = wintypes.BOOL
            if k32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = round(stat.ullTotalPhys / (1024.0 * 1024.0), 1)
                avail_mb = stat.ullAvailPhys / (1024.0 * 1024.0)
                used_mb = round(total_mb - avail_mb, 1)
                pct = round(float(stat.dwMemoryLoad), 1)
                return used_mb, total_mb, pct
        except Exception:
            pass

    return 0.0, 0.0, 0.0


def _get_fallback_cpu_percent() -> float:
    """Calculates process CPU percentage between calls using process_time / monotonic."""
    global _LAST_CPU_TIMES
    now_proc = time.process_time()
    now_mono = time.monotonic()
    delta_proc = now_proc - _LAST_CPU_TIMES["process_time"]
    delta_mono = now_mono - _LAST_CPU_TIMES["monotonic"]

    _LAST_CPU_TIMES["process_time"] = now_proc
    _LAST_CPU_TIMES["monotonic"] = now_mono

    if delta_mono > 0:
        return round(min(100.0, max(0.0, (delta_proc / delta_mono) * 100.0)), 1)
    return 0.0


def get_process_ram_mb() -> float:
    """Returns the current process RSS in MB (cached via get_system_metrics or instant fallback)."""
    if HAS_PSUTIL and _PSUTIL_PROC is not None:
        try:
            return round(_PSUTIL_PROC.memory_info().rss / (1024.0 * 1024.0), 1)
        except Exception:
            pass
    return _get_fallback_process_ram_mb()


def get_system_metrics() -> Dict[str, Any]:
    """Returns RAM, CPU and process metrics safely with 1.0s caching and native fallbacks."""
    global _LAST_METRICS, _LAST_METRICS_TIME

    now = time.monotonic()
    if _LAST_METRICS is not None and (now - _LAST_METRICS_TIME) < 1.0:
        return dict(_LAST_METRICS)

    psutil_success = False
    proc_ram: float = 0.0
    proc_cpu: float = 0.0
    sys_used: float = 0.0
    sys_total: float = 0.0
    sys_ram_pct: float = 0.0
    thread_count: int = threading.active_count()

    if HAS_PSUTIL and _PSUTIL_PROC is not None:
        try:
            mem_info = _PSUTIL_PROC.memory_info()
            proc_ram = round(mem_info.rss / (1024.0 * 1024.0), 1)
            proc_cpu = round(_PSUTIL_PROC.cpu_percent(interval=None), 1)
            vmem = psutil.virtual_memory()
            sys_used = round((vmem.total - vmem.available) / (1024.0 * 1024.0), 1)
            sys_total = round(vmem.total / (1024.0 * 1024.0), 1)
            sys_ram_pct = round(vmem.percent, 1)
            thread_count = _PSUTIL_PROC.num_threads()
            psutil_success = True
        except Exception:
            psutil_success = False

    if not psutil_success:
        proc_ram = _get_fallback_process_ram_mb()
        proc_cpu = _get_fallback_cpu_percent()
        sys_used, sys_total, sys_ram_pct = _get_fallback_system_ram()
        thread_count = threading.active_count()

    metrics = {
        "psutil_available": psutil_success,
        "process_ram_mb": proc_ram,
        "process_memory_mb": proc_ram,
        "cpu_percent": proc_cpu,
        "process_cpu": proc_cpu,
        "system_ram_percent": sys_ram_pct,
        "system_used_mb": sys_used,
        "system_total_mb": sys_total,
        "threads": thread_count,
    }

    _LAST_METRICS = dict(metrics)
    _LAST_METRICS_TIME = now
    return metrics


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
        return get_system_metrics()


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
                "ram_mb": get_process_ram_mb(),
                "ip": client_ip,
            })
