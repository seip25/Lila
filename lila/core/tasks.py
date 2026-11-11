"""Background tasks persisted in SQLite — no Redis needed.

    from lila.core.tasks import task

    @task(retries=3, timeout=120)
    async def send_welcome(user_id: int):
        ...

    await send_welcome.delay(user_id=7)              # run as soon as possible
    await send_welcome.delay(user_id=7, _in=60)      # in 60 seconds

Tasks live in ``app/data/lila_tasks.db`` (a separate file, so the queue never
locks the project's own SQLite database). Every web worker consumes them in
the background (``TASKS_IN_PROCESS=true``, ``TASK_CONCURRENCY=2``), or run a
dedicated process with ``lila worker --driver sqlite``. A task is claimed with
one atomic ``UPDATE ... RETURNING``, so several processes never run the same
task. Failures are retried with exponential backoff and end as ``dead``
after ``retries``. Arguments must be JSON-serializable (no pickle).
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import socket
import time
import traceback
from typing import Any, Callable, Dict, List, Optional

from lila.core import system_db
from lila.core.config import ENV_CONFIG
from lila.core.logger import Logger

DB_NAME = "lila_tasks"
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    timeout INTEGER NOT NULL DEFAULT 300,
    run_at REAL NOT NULL,
    locked_by TEXT,
    locked_at REAL,
    last_error TEXT,
    created_at REAL NOT NULL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS ix_tasks_ready ON tasks (status, run_at);
"""

_REGISTRY: Dict[str, "Task"] = {}
_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _conn():
    return system_db.connect(DB_NAME, SCHEMA)


def _allowed(module: str) -> bool:
    prefixes = tuple(p.strip() for p in str(os.environ.get("LILA_TASK_MODULES", "app.,lila.,main")).split(",") if p.strip())
    return not prefixes or module.startswith(prefixes)


class Task:
    """A registered function that can be queued with ``.delay()``."""

    def __init__(self, func: Callable, name: str, retries: int, timeout: int, backoff: float):
        self.func = func
        self.name = name
        self.retries = max(1, int(retries))
        self.timeout = max(1, int(timeout))
        self.backoff = float(backoff)
        self.__wrapped__ = func
        self.__name__ = getattr(func, "__name__", name)
        self.__doc__ = func.__doc__

    def __call__(self, *args, **kwargs):  # calling it directly still works
        return self.func(*args, **kwargs)

    async def delay(self, *args, _in: float = 0, _at: Optional[float] = None, **kwargs) -> int:
        return await enqueue(self.name, args=list(args), kwargs=kwargs, delay=_in, at=_at,
                             retries=self.retries, timeout=self.timeout)

    def delay_sync(self, *args, _in: float = 0, **kwargs) -> int:
        return enqueue_sync(self.name, args=list(args), kwargs=kwargs, delay=_in,
                            retries=self.retries, timeout=self.timeout)


def task(func: Optional[Callable] = None, *, name: Optional[str] = None, retries: int = 3,
         timeout: int = 300, backoff: float = 5.0):
    """Registers a background task (sync or async function)."""

    def decorator(fn: Callable) -> Task:
        task_name = name or f"{fn.__module__}:{fn.__qualname__}"
        wrapped = Task(fn, task_name, retries, timeout, backoff)
        _REGISTRY[task_name] = wrapped
        _ensure_lifecycle()
        return wrapped

    return decorator(func) if callable(func) else decorator


def enqueue_sync(name: str, args: Optional[list] = None, kwargs: Optional[dict] = None, delay: float = 0,
                 at: Optional[float] = None, retries: int = 3, timeout: int = 300) -> int:
    payload = json.dumps({"args": args or [], "kwargs": kwargs or {}}, default=str)
    now = time.time()
    run_at = at if at is not None else now + max(0.0, float(delay))
    cur = _conn().execute(
        "INSERT INTO tasks (name, payload, max_attempts, timeout, run_at, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, payload, int(retries), int(timeout), run_at, now),
    )
    _WAKE.set_threadsafe()
    return int(cur.lastrowid)


async def enqueue(name: str, args: Optional[list] = None, kwargs: Optional[dict] = None, delay: float = 0,
                  at: Optional[float] = None, retries: int = 3, timeout: int = 300) -> int:
    """Queues ``name`` (``"module:function"`` or a ``@task`` name). Returns the task id."""
    return await asyncio.to_thread(enqueue_sync, name, args, kwargs, delay, at, retries, timeout)


def _claim(worker_id: str) -> Optional[dict]:
    now = time.time()
    row = _conn().execute(
        """
        UPDATE tasks SET status = 'running', locked_by = ?, locked_at = ?, attempts = attempts + 1
        WHERE id = (
            SELECT id FROM tasks WHERE status = 'queued' AND run_at <= ? ORDER BY run_at, id LIMIT 1
        ) AND status = 'queued'
        RETURNING id, name, payload, attempts, max_attempts, timeout
        """,
        (worker_id, now, now),
    ).fetchone()
    return dict(row) if row else None


def _finish(task_id: int, ok: bool, error: str = "", attempts: int = 0, max_attempts: int = 1,
            backoff: float = 5.0) -> str:
    now = time.time()
    conn = _conn()
    if ok:
        conn.execute("UPDATE tasks SET status='done', finished_at=?, last_error=NULL WHERE id=?", (now, task_id))
        return "done"
    if attempts >= max_attempts:
        conn.execute("UPDATE tasks SET status='dead', finished_at=?, last_error=? WHERE id=?",
                     (now, error[-4000:], task_id))
        return "dead"
    wait = backoff * (2 ** max(0, attempts - 1))
    conn.execute(
        "UPDATE tasks SET status='queued', run_at=?, locked_by=NULL, locked_at=NULL, last_error=? WHERE id=?",
        (now + wait, error[-4000:], task_id),
    )
    return "retry"


def _requeue_stale() -> int:
    """Tasks left 'running' by a crashed process go back to the queue."""
    now = time.time()
    cur = _conn().execute(
        "UPDATE tasks SET status='queued', locked_by=NULL, locked_at=NULL "
        "WHERE status='running' AND locked_at < ? - (timeout * 2 + 30)",
        (now,),
    )
    return cur.rowcount


def _prune() -> None:
    hours = float(os.environ.get("TASK_KEEP_DONE_HOURS", "24") or 24)
    _conn().execute("DELETE FROM tasks WHERE status='done' AND finished_at < ?", (time.time() - hours * 3600,))


def resolve(name: str) -> Callable:
    registered = _REGISTRY.get(name)
    if registered is not None:
        return registered.func
    module_name, _, qualname = name.partition(":")
    if not qualname or not _allowed(module_name):
        raise LookupError(f"Task '{name}' is not registered (or its module is not in LILA_TASK_MODULES)")
    obj: Any = importlib.import_module(module_name)
    for attr in qualname.split("."):
        obj = getattr(obj, attr)
    return obj.func if isinstance(obj, Task) else obj


async def run_one(worker_id: str = _WORKER_ID) -> Optional[str]:
    """Claims and runs one task. Returns its final state or None if idle."""
    job = await asyncio.to_thread(_claim, worker_id)
    if job is None:
        return None
    backoff = _REGISTRY[job["name"]].backoff if job["name"] in _REGISTRY else 5.0
    try:
        func = resolve(job["name"])
        data = json.loads(job["payload"])
        if inspect.iscoroutinefunction(func):
            await asyncio.wait_for(func(*data.get("args", []), **data.get("kwargs", {})), timeout=job["timeout"])
        else:
            await asyncio.wait_for(
                asyncio.to_thread(func, *data.get("args", []), **data.get("kwargs", {})), timeout=job["timeout"]
            )
        state = await asyncio.to_thread(_finish, job["id"], True)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=5)}"
        state = await asyncio.to_thread(_finish, job["id"], False, error, job["attempts"], job["max_attempts"], backoff)
        Logger.error(f"[Lila tasks] {job['name']} #{job['id']} failed ({state}): {exc}")
    return state


class _Wake:
    """Wakes idle consumers right after a task is queued in this process."""

    def __init__(self):
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.event: Optional[asyncio.Event] = None

    def bind(self):
        self.loop = asyncio.get_running_loop()
        self.event = asyncio.Event()

    def set_threadsafe(self):
        if self.loop is not None and self.event is not None and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.event.set)
            except RuntimeError:
                pass


_WAKE = _Wake()
_consumers: List[asyncio.Task] = []


async def _consumer(index: int) -> None:
    idle = 0.2
    while True:
        try:
            state = await run_one(f"{_WORKER_ID}#{index}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            Logger.error(f"[Lila tasks] consumer error: {exc}")
            state = None
        if state is not None:
            idle = 0.2
            continue
        try:
            await asyncio.wait_for(_WAKE.event.wait(), timeout=idle)
        except asyncio.TimeoutError:
            pass
        _WAKE.event.clear()
        idle = min(idle * 2, 2.0)  # 0.2s → 2s while the queue stays empty


async def _maintenance() -> None:
    while True:
        try:
            await asyncio.to_thread(_requeue_stale)
            await asyncio.to_thread(_prune)
        except Exception:
            pass
        await asyncio.sleep(60)


async def start_consumers(concurrency: Optional[int] = None) -> None:
    if _consumers:
        return
    _WAKE.bind()
    count = int(concurrency or ENV_CONFIG.get("TASK_CONCURRENCY", 2) or 2)
    for i in range(max(1, count)):
        _consumers.append(asyncio.create_task(_consumer(i)))
    _consumers.append(asyncio.create_task(_maintenance()))


async def stop_consumers() -> None:
    for job in _consumers:
        job.cancel()
    for job in _consumers:
        try:
            await job
        except (asyncio.CancelledError, Exception):
            pass
    _consumers.clear()


def stats() -> Dict[str, int]:
    rows = _conn().execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


def list_tasks(status: Optional[str] = None, limit: int = 50) -> List[dict]:
    sql = "SELECT id, name, status, attempts, max_attempts, run_at, last_error, created_at FROM tasks"
    params: tuple = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY id DESC LIMIT ?"
    return [dict(r) for r in _conn().execute(sql, params + (int(limit),)).fetchall()]


def retry(task_id: int) -> bool:
    cur = _conn().execute(
        "UPDATE tasks SET status='queued', run_at=?, attempts=0, last_error=NULL WHERE id=? AND status IN ('dead','done')",
        (time.time(), int(task_id)),
    )
    return cur.rowcount > 0


def purge(status: str = "done") -> int:
    return _conn().execute("DELETE FROM tasks WHERE status = ?", (status,)).rowcount


_LIFECYCLE = False


def _ensure_lifecycle() -> None:
    """The first @task registers start/stop hooks on the App lifespan."""
    global _LIFECYCLE
    if _LIFECYCLE:
        return
    _LIFECYCLE = True
    from lila.core.app import register_lifecycle

    async def _start(app):
        if str(ENV_CONFIG.get("TASKS_IN_PROCESS", "true")).lower() not in ("0", "false", "no"):
            await start_consumers()

    async def _stop(app):
        await stop_consumers()

    register_lifecycle(_start, _stop)
