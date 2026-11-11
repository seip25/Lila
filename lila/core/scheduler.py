"""Scheduled jobs without Redis or cron: ``@every`` and ``@cron``.

    from lila.core.scheduler import every, cron

    @every(minutes=10)
    async def refresh_rates(): ...

    @cron("0 3 * * *")                 # every day at 03:00 (server local time)
    def nightly_backup(): ...

    @cron("*/15 9-18 * * mon-fri", queue=True)   # hand it to the SQLite task queue

Jobs start with the App (import the module that defines them from ``main.py``).
With several workers only **one** process runs the schedule: the leader holds
an OS file lock on ``app/data/scheduler.lock``; if it dies the lock is freed
and another worker takes over. A job never overlaps with itself, sync jobs run
in a thread, and the last run of each job is kept in ``lila_system.db`` so a
restart does not repeat an ``@every`` job early.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import inspect
import os
import time
from typing import Callable, Dict, List, Optional, Set

from lila.core import system_db
from lila.core.config import ENV_CONFIG
from lila.core.logger import Logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_runs (
    name TEXT PRIMARY KEY,
    last_run REAL,
    last_status TEXT,
    last_error TEXT,
    last_duration REAL
);
"""

_DOW_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
_MON_NAMES = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def _parse_field(expr: str, low: int, high: int, names: Optional[dict] = None) -> Set[int]:
    values: Set[int] = set()
    for part in expr.lower().split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
            if step < 1:
                raise ValueError("cron step must be >= 1")
        if part in ("*", ""):
            start, end = low, high
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = _value(a, names), _value(b, names)
        else:
            start = _value(part, names)
            end = high if step > 1 else start
        if start < low or end > high or start > end:
            raise ValueError(f"cron value out of range: {expr}")
        values.update(range(start, end + 1, step))
    return values


def _value(token: str, names: Optional[dict]) -> int:
    token = token.strip().lower()
    if names and token[:3] in names:
        return names[token[:3]]
    return int(token)


class CronSchedule:
    """Standard 5-field cron: minute hour day-of-month month day-of-week."""

    def __init__(self, expression: str):
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError("cron expressions need 5 fields: 'min hour day month weekday'")
        self.expression = expression
        self.minutes = _parse_field(fields[0], 0, 59)
        self.hours = _parse_field(fields[1], 0, 23)
        self.days = _parse_field(fields[2], 1, 31)
        self.months = _parse_field(fields[3], 1, 12, _MON_NAMES)
        # 0 and 7 are both Sunday ("5-7" = Fri..Sun).
        self.weekdays = {0 if v == 7 else v for v in _parse_field(fields[4], 0, 7, _DOW_NAMES)}
        self.dom_any = fields[2] == "*"
        self.dow_any = fields[4] == "*"

    def _day_ok(self, d: _dt.datetime) -> bool:
        dom = d.day in self.days
        dow = (d.weekday() + 1) % 7 in self.weekdays
        if self.dom_any and self.dow_any:
            return True
        if self.dom_any:
            return dow
        if self.dow_any:
            return dom
        return dom or dow  # classic cron: either matches

    def next_after(self, after: _dt.datetime) -> _dt.datetime:
        d = after.replace(second=0, microsecond=0) + _dt.timedelta(minutes=1)
        limit = after + _dt.timedelta(days=366 * 5)
        while d <= limit:
            if d.month not in self.months:
                d = (d.replace(day=1, hour=0, minute=0) + _dt.timedelta(days=32)).replace(day=1)
                continue
            if not self._day_ok(d):
                d = (d + _dt.timedelta(days=1)).replace(hour=0, minute=0)
                continue
            if d.hour not in self.hours:
                d = (d + _dt.timedelta(hours=1)).replace(minute=0)
                continue
            if d.minute not in self.minutes:
                d += _dt.timedelta(minutes=1)
                continue
            return d
        raise ValueError(f"cron '{self.expression}' never matches")


class Job:
    def __init__(self, func: Callable, name: str, interval: Optional[float] = None,
                 cron_expr: Optional[str] = None, run_on_start: bool = False, queue: bool = False):
        self.func = func
        self.name = name
        self.interval = interval
        self.cron = CronSchedule(cron_expr) if cron_expr else None
        self.run_on_start = run_on_start
        self.queue = queue
        self.running = False
        self.next_run: float = 0.0

    def schedule_next(self, last_run: Optional[float], now: float) -> None:
        if self.cron is not None:
            self.next_run = self.cron.next_after(_dt.datetime.fromtimestamp(now)).timestamp()
        elif last_run and not self.run_on_start:
            self.next_run = max(now, last_run + self.interval)
        elif self.run_on_start:
            self.next_run = now
        else:
            self.next_run = now + self.interval

    def describe(self) -> str:
        return f"cron '{self.cron.expression}'" if self.cron else f"every {self.interval:g}s"


_JOBS: Dict[str, Job] = {}


def _register(job: Job) -> Callable:
    _JOBS[job.name] = job
    _ensure_lifecycle()
    return job.func


def every(seconds: float = 0, minutes: float = 0, hours: float = 0, days: float = 0, *,
          name: Optional[str] = None, run_on_start: bool = False, queue: bool = False):
    """Runs the function at a fixed interval (minimum 1 second)."""
    interval = seconds + minutes * 60 + hours * 3600 + days * 86400
    if interval < 1:
        raise ValueError("@every needs an interval of at least 1 second")

    def decorator(fn: Callable) -> Callable:
        return _register(Job(fn, name or f"{fn.__module__}:{fn.__qualname__}", interval=interval,
                             run_on_start=run_on_start, queue=queue))

    return decorator


def cron(expression: str, *, name: Optional[str] = None, queue: bool = False):
    """Runs the function on a cron schedule (server local time)."""
    CronSchedule(expression)  # validate at import time

    def decorator(fn: Callable) -> Callable:
        return _register(Job(fn, name or f"{fn.__module__}:{fn.__qualname__}", cron_expr=expression, queue=queue))

    return decorator


def jobs() -> List[Job]:
    return list(_JOBS.values())


def last_runs() -> Dict[str, dict]:
    rows = system_db.connect("lila_system", _SCHEMA).execute("SELECT * FROM scheduler_runs").fetchall()
    return {r["name"]: dict(r) for r in rows}


def _save_run(name: str, started: float, status: str, error: str, duration: float) -> None:
    system_db.connect("lila_system", _SCHEMA).execute(
        "INSERT INTO scheduler_runs (name, last_run, last_status, last_error, last_duration) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET last_run=excluded.last_run, last_status=excluded.last_status, "
        "last_error=excluded.last_error, last_duration=excluded.last_duration",
        (name, started, status, error[-2000:] if error else None, duration),
    )


async def run_job(job: Job) -> str:
    """Runs one job now (used by the loop and by ``lila schedule run``)."""
    if job.running:
        return "skipped"
    job.running = True
    started = time.time()
    status, error = "ok", ""
    try:
        if job.queue:
            from lila.core.tasks import enqueue

            await enqueue(f"{job.func.__module__}:{job.func.__qualname__}")
            status = "queued"
        elif inspect.iscoroutinefunction(job.func):
            await job.func()
        else:
            await asyncio.to_thread(job.func)
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        Logger.error(f"[Lila scheduler] {job.name} failed: {exc}", exception=exc)
    finally:
        job.running = False
    await asyncio.to_thread(_save_run, job.name, started, status, error, time.time() - started)
    return status


class _LeaderLock:
    """Non-blocking OS file lock: exactly one process per machine runs the schedule."""

    def __init__(self, path: str):
        self.path = path
        self.fh = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fh = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self.fh = fh
        return True

    def release(self) -> None:
        if self.fh is not None:
            try:
                self.fh.close()  # closing the descriptor releases the lock
            finally:
                self.fh = None


_loop_task: Optional[asyncio.Task] = None
_lock: Optional[_LeaderLock] = None


async def _scheduler_loop() -> None:
    global _lock
    _lock = _LeaderLock(os.path.join(os.path.dirname(system_db.system_db_path()), "scheduler.lock"))
    while not _lock.acquire():
        await asyncio.sleep(30)  # another worker is the leader; retry in case it stops
    try:
        runs = await asyncio.to_thread(last_runs)
        now = time.time()
        for job in _JOBS.values():
            job.schedule_next((runs.get(job.name) or {}).get("last_run"), now)
        running: Set[asyncio.Task] = set()
        while True:
            now = time.time()
            for job in list(_JOBS.values()):
                if job.next_run <= now and not job.running:
                    t = asyncio.create_task(run_job(job))
                    running.add(t)
                    t.add_done_callback(running.discard)
                    if job.cron:
                        job.next_run = job.cron.next_after(_dt.datetime.fromtimestamp(now)).timestamp()
                    else:
                        job.next_run = now + job.interval
            upcoming = min((j.next_run for j in _JOBS.values()), default=now + 30)
            await asyncio.sleep(max(0.5, min(30.0, upcoming - time.time())))
    finally:
        _lock.release()


async def start() -> None:
    global _loop_task
    if _loop_task is None and _JOBS:
        _loop_task = asyncio.create_task(_scheduler_loop())


async def stop() -> None:
    global _loop_task
    if _loop_task is not None:
        _loop_task.cancel()
        try:
            await _loop_task
        except (asyncio.CancelledError, Exception):
            pass
        _loop_task = None


_LIFECYCLE = False


def _ensure_lifecycle() -> None:
    global _LIFECYCLE
    if _LIFECYCLE:
        return
    _LIFECYCLE = True
    from lila.core.app import register_lifecycle

    async def _start(app):
        if str(ENV_CONFIG.get("SCHEDULER_ENABLED", "true")).lower() not in ("0", "false", "no"):
            await start()

    async def _stop(app):
        await stop()

    register_lifecycle(_start, _stop)
