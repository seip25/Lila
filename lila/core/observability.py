"""Health checks and Prometheus metrics that never leak data.

``/health`` (on by default, unless you define your own route) answers only
``{"status": "ok"}`` (200) or ``{"status": "error"}`` (503): no versions,
paths, errors or hostnames. The database check is cached for 5 seconds.

``/health/details`` and ``/metrics`` (``App(metrics=True)``) are protected:

1. ``METRICS_TOKEN`` set → ``Authorization: Bearer <token>`` required
   (constant-time compare). Use this for Prometheus.
2. no token → only direct loopback clients (``127.0.0.1``/``::1``) without
   proxy headers: anything relayed by Nginx is refused, even when the server
   runs without ``--proxy-headers``.
3. ``METRICS_OTP=true`` → on top of 1/2, each access needs a one-time code:
   the server prints a 6-digit code in its terminal/log (valid 5 minutes,
   single use) and the client repeats the request with ``X-Lila-OTP: <code>``
   or ``?otp=<code>``. Codes are stored hashed in ``lila_system.db``.

Metrics carry no path, user or query labels (no cardinality explosion and no
personal data): request counts by method and status class, a latency
histogram, requests in flight, process RSS/CPU/threads/FDs, cache and task
queue sizes.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import sys
import threading
import time
from typing import Dict, Optional, Tuple

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from lila.core.config import ENV_CONFIG
from lila.core.logger import Logger
from lila.core.responses import JSONResponse

_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


class _Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests: Dict[Tuple[str, str], int] = {}
        self.buckets = [0] * (len(_BUCKETS) + 1)
        self.duration_sum = 0.0
        self.duration_count = 0
        self.in_flight = 0
        self.started = time.time()

    def observe(self, method: str, status: int, seconds: float) -> None:
        key = (method, f"{status // 100}xx")
        with self.lock:
            self.requests[key] = self.requests.get(key, 0) + 1
            self.duration_sum += seconds
            self.duration_count += 1
            for i, bound in enumerate(_BUCKETS):
                if seconds <= bound:
                    self.buckets[i] += 1
                    break
            else:
                self.buckets[-1] += 1


METRICS = _Metrics()


class PureASGIMetricsMiddleware:
    """Counts requests (method + status class only) and their latency."""

    __slots__ = ("app",)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or scope.get("path") in ("/metrics", "/health", "/health/details"):
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500
        METRICS.in_flight += 1

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            METRICS.in_flight -= 1
            METRICS.observe(scope.get("method", "GET"), status, time.perf_counter() - start)


# ── Health ─────────────────────────────────────────────────────────────────────
_health_cache: Dict[str, float] = {"at": 0.0, "ok": 0.0}


async def _database_ok() -> bool:
    now = time.monotonic()
    if now - _health_cache["at"] < 5:
        return bool(_health_cache["ok"])
    ok = True
    try:
        from sqlalchemy import text

        try:
            from app.connections import connection as db  # project database
        except Exception:
            from lila.core.database import db
        if getattr(db, "engine", None) is not None and getattr(db, "is_async", False):
            async def _ping():
                async with db.engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            await asyncio.wait_for(_ping(), timeout=2)
    except Exception as exc:
        ok = False
        Logger.error(f"[Lila health] database check failed: {exc}")
    _health_cache.update(at=now, ok=1.0 if ok else 0.0)
    return ok


async def health_endpoint(request):
    ok = await _database_ok()
    return JSONResponse({"status": "ok" if ok else "error"}, status_code=200 if ok else 503,
                        headers={"Cache-Control": "no-store"})


# ── Access control ─────────────────────────────────────────────────────────────
_OTP_SCHEMA = """
CREATE TABLE IF NOT EXISTS lila_otp (
    code_hash TEXT PRIMARY KEY,
    expires_at REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
"""
_OTP_TTL = 300


def _otp_store():
    from lila.core import system_db

    return system_db.connect("lila_system", _OTP_SCHEMA)


def _otp_hash(code: str) -> str:
    from lila.core.config import get_secret_key

    return hmac.new(get_secret_key().encode(), code.encode(), hashlib.sha256).hexdigest()


def issue_otp(path: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    store = _otp_store()
    store.execute("DELETE FROM lila_otp WHERE expires_at < ? OR used = 1", (time.time(),))
    store.execute("INSERT OR REPLACE INTO lila_otp (code_hash, expires_at) VALUES (?, ?)",
                  (_otp_hash(code), time.time() + _OTP_TTL))
    message = f"[Lila] One-time code for {path}: {code} (valid 5 minutes, single use)"
    print(message, file=sys.stderr, flush=True)
    Logger.warning(f"[Lila] One-time code issued for {path}")  # the code itself is never logged to files
    return code


def consume_otp(code: str) -> bool:
    if not code or not code.isdigit() or len(code) != 6:
        return False
    cur = _otp_store().execute(
        "UPDATE lila_otp SET used = 1 WHERE code_hash = ? AND used = 0 AND expires_at >= ?",
        (_otp_hash(code), time.time()),
    )
    return cur.rowcount == 1


def check_private_access(request) -> Optional[JSONResponse]:
    """``None`` when the caller may see private health/metrics data."""
    token = str(ENV_CONFIG.get("METRICS_TOKEN", "") or os.environ.get("METRICS_TOKEN", "") or "")
    if token:
        auth = request.headers.get("authorization", "")
        given = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not given or not hmac.compare_digest(given.encode(), token.encode()):
            return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401,
                                headers={"WWW-Authenticate": "Bearer"})
    else:
        host = getattr(request.client, "host", "") if request.client else ""
        # Requests relayed by a proxy carry forwarding headers: even if the
        # server was started without --proxy-headers (so every client looks
        # like 127.0.0.1), they are refused without a token.
        proxied = any(request.headers.get(h) for h in ("x-forwarded-for", "x-real-ip", "forwarded"))
        if host not in _LOOPBACK or proxied:
            return JSONResponse({"success": False, "message": "Not found"}, status_code=404)
    if str(ENV_CONFIG.get("METRICS_OTP", "") or os.environ.get("METRICS_OTP", "")).lower() in ("1", "true", "yes", "on"):
        code = request.headers.get("x-lila-otp") or request.query_params.get("otp") or ""
        if not consume_otp(code.strip()):
            issue_otp(request.url.path)
            return JSONResponse(
                {"success": False, "otp_required": True,
                 "message": "A one-time code was printed in the server terminal. Repeat with X-Lila-OTP."},
                status_code=401,
            )
    return None


# ── Endpoints ──────────────────────────────────────────────────────────────────
def _process_stats() -> Dict[str, float]:
    stats: Dict[str, float] = {"threads": float(threading.active_count())}
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        stats["cpu_seconds"] = usage.ru_utime + usage.ru_stime
    except Exception:
        pass
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    stats["rss_bytes"] = float(int(line.split()[1]) * 1024)
        stats["open_fds"] = float(len(os.listdir("/proc/self/fd")))
    except Exception:
        try:
            from lila.core.debug import get_system_metrics

            stats["rss_bytes"] = float(get_system_metrics().get("process_ram_mb", 0)) * 1024 * 1024
        except Exception:
            pass
    return stats


async def health_details_endpoint(request):
    denied = check_private_access(request)
    if denied is not None:
        return denied
    from lila.core.cache import Cache

    data = {
        "status": "ok" if await _database_ok() else "error",
        "uptime_seconds": round(time.time() - METRICS.started),
        "process": _process_stats(),
        "cache": Cache.stats(),
    }
    try:
        from lila.core import tasks

        if tasks._REGISTRY or tasks._consumers:
            data["tasks"] = await asyncio.to_thread(tasks.stats)
    except Exception:
        pass
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


async def metrics_endpoint(request):
    denied = check_private_access(request)
    if denied is not None:
        return denied
    lines = [
        "# HELP lila_requests_total HTTP requests by method and status class.",
        "# TYPE lila_requests_total counter",
    ]
    with METRICS.lock:
        requests = dict(METRICS.requests)
        buckets = list(METRICS.buckets)
        total_sum, total_count = METRICS.duration_sum, METRICS.duration_count
    for (method, status), count in sorted(requests.items()):
        lines.append(f'lila_requests_total{{method="{method}",status="{status}"}} {count}')
    lines += [
        "# HELP lila_request_duration_seconds Request latency.",
        "# TYPE lila_request_duration_seconds histogram",
    ]
    cumulative = 0
    for bound, count in zip(_BUCKETS, buckets):
        cumulative += count
        lines.append(f'lila_request_duration_seconds_bucket{{le="{bound}"}} {cumulative}')
    lines.append(f'lila_request_duration_seconds_bucket{{le="+Inf"}} {cumulative + buckets[-1]}')
    lines.append(f"lila_request_duration_seconds_sum {total_sum:.6f}")
    lines.append(f"lila_request_duration_seconds_count {total_count}")
    lines += ["# TYPE lila_requests_in_flight gauge", f"lila_requests_in_flight {METRICS.in_flight}"]
    proc = _process_stats()
    if "rss_bytes" in proc:
        lines += ["# TYPE process_resident_memory_bytes gauge", f"process_resident_memory_bytes {proc['rss_bytes']:.0f}"]
    if "cpu_seconds" in proc:
        lines += ["# TYPE process_cpu_seconds_total counter", f"process_cpu_seconds_total {proc['cpu_seconds']:.3f}"]
    if "open_fds" in proc:
        lines += ["# TYPE process_open_fds gauge", f"process_open_fds {proc['open_fds']:.0f}"]
    lines += ["# TYPE process_threads gauge", f"process_threads {proc['threads']:.0f}",
              "# TYPE lila_uptime_seconds gauge", f"lila_uptime_seconds {time.time() - METRICS.started:.0f}"]
    try:
        from lila.core.cache import Cache

        cache = Cache.stats()
        lines += ["# TYPE lila_cache_items gauge", f"lila_cache_items {cache.get('memory_items', 0)}",
                  "# TYPE lila_cache_memory_bytes gauge",
                  f"lila_cache_memory_bytes {int(float(cache.get('memory_mb', 0)) * 1024 * 1024)}"]
    except Exception:
        pass
    try:
        from lila.core import tasks

        if tasks._REGISTRY or tasks._consumers:
            lines.append("# TYPE lila_tasks gauge")
            for status, count in sorted((await asyncio.to_thread(tasks.stats)).items()):
                lines.append(f'lila_tasks{{status="{status}"}} {count}')
    except Exception:
        pass
    lines += ["# TYPE lila_database_up gauge", f"lila_database_up {1 if await _database_ok() else 0}"]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4",
                             headers={"Cache-Control": "no-store"})
