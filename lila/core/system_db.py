"""Small SQLite files for framework state, separate from the project database.

``lila_system.db`` (migration history, scheduler state) and ``lila_tasks.db``
(task queue) live in ``app/data/`` (or the OS app-data folder when frozen),
so framework writes never lock the application's own SQLite database and also
work when the project uses MySQL/PostgreSQL.

Uses the stdlib ``sqlite3`` module (WAL, busy timeout); async callers run the
short queries in a thread with ``asyncio.to_thread``.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Dict

from lila.core.config import ENV_CONFIG, get_data_path

_local = threading.local()
_init_lock = threading.Lock()
_initialized: Dict[str, bool] = {}


def system_db_path(name: str = "lila_system") -> str:
    # The live environment wins (tests/processes may change it after .env loaded).
    folder = os.environ.get("LILA_DATA_DIR") or str(ENV_CONFIG.get("LILA_DATA_DIR", "") or "") or get_data_path("app", "data")
    return os.path.join(folder, f"{name}.db")


def connect(name: str = "lila_system", schema: str = "") -> sqlite3.Connection:
    """Thread-local connection to a framework SQLite file (created on demand)."""
    path = system_db_path(name)
    conns = getattr(_local, "conns", None)
    if conns is None:
        conns = _local.conns = {}
    conn = conns.get(path)
    if conn is not None:
        return conn
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=10000")
    if schema:
        with _init_lock:
            key = f"{path}:{hash(schema)}"
            if not _initialized.get(key):
                conn.executescript(schema)
                _initialized[key] = True
    conns[path] = conn
    return conn


def close_all() -> None:
    conns = getattr(_local, "conns", None) or {}
    for conn in conns.values():
        try:
            conn.close()
        except Exception:
            pass
    conns.clear()
    _initialized.clear()
