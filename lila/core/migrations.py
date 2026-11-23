"""Schema diff ("plan") and safe migrations with history.

``lila migrate --plan`` lists what differs between the models and the
database; ``lila migrate`` applies the **safe** operations:

- ``create_table``   missing tables
- ``add_column``     missing columns (nullable or with a default)
- ``rename_column``  declared on the model: ``__renamed_columns__ = {"new": "old"}``
- ``create_index``   ``Column(index=True)`` / ``Index(...)`` missing in the DB

and only reports the ones that need a human decision:

- ``alter_type`` / ``alter_nullable``  type or NULL changes (data may not fit)
- ``add_column_manual``                NOT NULL column without a default
- ``drop_column``                      columns in the DB that the model lost
                                       (applied only with ``--drop-columns``)

Every applied operation is recorded in ``app/data/lila_system.db``
(``lila migrate history``), never in the project database, grouped in
batches (one per ``lila migrate`` run). ``lila migrate rollback`` undoes the
last batch: index and rename steps directly; columns and tables the batch
added only with confirmation (their data is lost). Dropped columns cannot
be restored.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import importlib
import inspect
import os
import pkgutil
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import inspect as sa_inspect, text

from lila.core.config import ENV_CONFIG, get_data_path
from lila.core.logger import Logger

SAFE_KINDS = {"create_table", "add_column", "rename_column", "create_index"}

_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS lila_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applied_at TEXT NOT NULL,
    database TEXT NOT NULL,
    kind TEXT NOT NULL,
    target TEXT NOT NULL,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS lila_script_migrations (
    database TEXT NOT NULL,
    name TEXT NOT NULL,
    app_version TEXT NOT NULL DEFAULT '',
    applied_at TEXT NOT NULL,
    PRIMARY KEY (database, name)
);
"""

_SCRIPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS lila_script_migrations (
    database TEXT NOT NULL,
    name TEXT NOT NULL,
    app_version TEXT NOT NULL DEFAULT '',
    applied_at TEXT NOT NULL,
    PRIMARY KEY (database, name)
);
"""

_LAST_AUTO_MIGRATE_REPORT: Dict[str, Any] = {
    "backup_path": None,
    "applied_ops": [],
    "applied_scripts": [],
}


def _norm_type(value: str) -> str:
    value = re.sub(r"\s+", "", str(value or "").upper())
    aliases = {"INT": "INTEGER", "BOOL": "BOOLEAN", "DOUBLE": "FLOAT", "REAL": "FLOAT", "TIMESTAMP": "DATETIME"}
    base = value.split("(")[0]
    return aliases.get(base, base) + value[len(base):]


def _op(kind: str, table: str, detail: str, column: Optional[str] = None, **extra) -> Dict[str, Any]:
    return {
        "kind": kind,
        "table": table,
        "column": column,
        "target": f"{table}.{column}" if column else table,
        "detail": detail,
        "safe": kind in SAFE_KINDS,
        **extra,
    }


def _model_for_table(table) -> Any:
    from lila.core.database import Base

    for mapper in Base.registry.mappers:
        if getattr(mapper, "local_table", None) is table:
            return mapper.class_
    return None


def build_plan(sync_conn, metadata) -> List[Dict[str, Any]]:
    """Compares ``metadata`` with the live schema (runs inside ``run_sync``)."""
    from lila.core.database import _scalar_default

    inspector = sa_inspect(sync_conn)
    dialect = sync_conn.dialect
    existing_tables = set(inspector.get_table_names())
    ops: List[Dict[str, Any]] = []
    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            ops.append(_op("create_table", table.name, f"{len(table.columns)} columns"))
            continue
        db_cols = {c["name"]: c for c in inspector.get_columns(table.name)}
        model = _model_for_table(table)
        renames = dict(getattr(model, "__renamed_columns__", {}) or {})
        for column in table.columns:
            old = renames.get(column.name) or (column.info or {}).get("renamed_from")
            if column.name not in db_cols:
                if old and old in db_cols:
                    ops.append(_op("rename_column", table.name, f"{old} → {column.name}", column.name, old=old))
                    continue
                if column.primary_key:
                    continue
                if not column.nullable and column.server_default is None and _scalar_default(column) is None:
                    ops.append(_op("add_column_manual", table.name,
                                   "NOT NULL without default: add a default/server_default or fill it manually",
                                   column.name))
                else:
                    ops.append(_op("add_column", table.name, str(column.type.compile(dialect=dialect)), column.name))
                continue
            current = db_cols[column.name]
            try:
                model_type = _norm_type(column.type.compile(dialect=dialect))
            except Exception:
                model_type = _norm_type(str(column.type))
            db_type = _norm_type(str(current.get("type")))
            if model_type and db_type and model_type != db_type and dialect.name != "sqlite":
                ops.append(_op("alter_type", table.name, f"{db_type} → {model_type}", column.name))
            elif dialect.name == "sqlite" and model_type.split("(")[0] != db_type.split("(")[0]:
                ops.append(_op("alter_type", table.name, f"{db_type} → {model_type}", column.name))
            if not column.primary_key and bool(current.get("nullable", True)) != bool(column.nullable):
                ops.append(_op("alter_nullable", table.name,
                               f"nullable {current.get('nullable')} → {column.nullable}", column.name))
        renamed_sources = set(renames.values()) | {
            (c.info or {}).get("renamed_from") for c in table.columns if (c.info or {}).get("renamed_from")
        }
        model_cols = {c.name for c in table.columns}
        for name in db_cols:
            if name not in model_cols and name not in renamed_sources:
                ops.append(_op("drop_column", table.name, "in the database but not in the model", name))
        db_indexes = {ix["name"] for ix in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name and index.name not in db_indexes:
                cols = ", ".join(c.name for c in index.columns)
                ops.append(_op("create_index", table.name, f"{index.name} ({cols})", index_name=index.name))
    return ops


_HISTORY_COLUMNS = {
    "batch": "INTEGER NOT NULL DEFAULT 0",
    "extra": "TEXT",            # JSON: table, column, old name, index name
    "rolled_back": "INTEGER NOT NULL DEFAULT 0",
}

# Inverse of each recorded operation. ``destructive`` ones lose data.
REVERSIBLE = {
    "create_index": ("drop_index", False),
    "rename_column": ("rename_back", False),
    "add_column": ("drop_column", True),
    "create_table": ("drop_table", True),
}


def _history_conn():
    """lila_migrations in app/data/lila_system.db (columns added for old files)."""
    from lila.core import system_db

    conn = system_db.connect("lila_system", _HISTORY_SCHEMA)
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(lila_migrations)").fetchall()}
    for name, ddl in _HISTORY_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE lila_migrations ADD COLUMN {name} {ddl}")
    conn.executescript(_SCRIPT_SCHEMA)
    return conn


def _record(database: str, applied: List[Dict[str, Any]]) -> int:
    """Stores one batch (a `lila migrate` run); returns its number."""
    if not applied:
        return 0
    import json

    conn = _history_conn()
    batch = int(conn.execute("SELECT COALESCE(MAX(batch), 0) + 1 FROM lila_migrations").fetchone()[0])
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO lila_migrations (applied_at, database, kind, target, detail, batch, extra) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (now, database, op["kind"], op["target"], op["detail"], batch, json.dumps({
                "table": op.get("table"), "column": op.get("column"), "old": op.get("old"),
                "index_name": op.get("index_name"),
            }))
            for op in applied
        ],
    )
    return batch


def history(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _history_conn()
    rows = conn.execute(
        "SELECT id, applied_at, database, kind, target, detail, batch, rolled_back FROM lila_migrations "
        "ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]


def rollback_plan(database: str, steps: int = 1) -> List[Dict[str, Any]]:
    """Operations of the last ``steps`` batches (newest first) and how to undo them."""
    import json

    conn = _history_conn()
    batches = [
        row[0] for row in conn.execute(
            "SELECT DISTINCT batch FROM lila_migrations WHERE database = ? AND rolled_back = 0 AND batch > 0 "
            "AND kind NOT LIKE 'rollback:%' ORDER BY batch DESC LIMIT ?",
            (database, int(steps)),
        ).fetchall()
    ]
    if not batches:
        return []
    marks = ",".join("?" for _ in batches)
    rows = conn.execute(
        f"SELECT id, batch, kind, target, detail, extra FROM lila_migrations WHERE database = ? AND batch IN ({marks}) "
        "AND rolled_back = 0 ORDER BY id DESC",
        (database, *batches),
    ).fetchall()
    plan = []
    for row in rows:
        extra = json.loads(row["extra"] or "{}")
        inverse, destructive = REVERSIBLE.get(row["kind"], (None, False))
        plan.append({
            "id": row["id"], "batch": row["batch"], "kind": row["kind"], "target": row["target"],
            "detail": row["detail"], "inverse": inverse, "destructive": destructive,
            "reversible": inverse is not None, **extra,
        })
    return plan


def database_key(db) -> str:
    url = db.engine.url
    return f"{url.get_backend_name()}:{url.database or ''}"


async def rollback_async(db, plan: List[Dict[str, Any]], allow_destructive: bool = False) -> List[Dict[str, Any]]:
    """Undoes a rollback plan (newest first). Destructive steps need ``allow_destructive``."""
    if not db._connected or db.engine is None:
        db.connect()
    undone: List[Dict[str, Any]] = []
    async with db.engine.begin() as conn:
        dialect = conn.dialect
        q = dialect.identifier_preparer.quote
        for op in plan:
            if not op["reversible"]:
                continue
            if op["destructive"] and not allow_destructive:
                continue
            table, column = op.get("table"), op.get("column")
            inverse = op["inverse"]
            if inverse == "drop_index":
                name = q(op["index_name"])
                if dialect.name == "mysql":
                    await conn.execute(text(f"DROP INDEX {name} ON {q(table)}"))
                else:
                    await conn.execute(text(f"DROP INDEX IF EXISTS {name}"))
            elif inverse == "rename_back":
                await conn.execute(text(f"ALTER TABLE {q(table)} RENAME COLUMN {q(column)} TO {q(op['old'])}"))
            elif inverse == "drop_column":
                await conn.execute(text(f"ALTER TABLE {q(table)} DROP COLUMN {q(column)}"))
            elif inverse == "drop_table":
                await conn.execute(text(f"DROP TABLE IF EXISTS {q(table)}"))
            undone.append(op)
    if undone:
        def _mark():
            hist = _history_conn()
            now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
            hist.executemany("UPDATE lila_migrations SET rolled_back = 1 WHERE id = ?", [(op["id"],) for op in undone])
            hist.executemany(
                "INSERT INTO lila_migrations (applied_at, database, kind, target, detail, batch, rolled_back) "
                "VALUES (?, ?, ?, ?, ?, 0, 1)",
                [(now, database_key(db), f"rollback:{op['kind']}", op["target"], op["inverse"]) for op in undone],
            )

        await asyncio.to_thread(_mark)
    return undone


async def plan_async(db, metadata=None) -> List[Dict[str, Any]]:
    from lila.core.database import Base

    if not db._connected or db.engine is None:
        db.connect()
    metadata = metadata or Base.metadata
    async with db.engine.connect() as conn:
        return await conn.run_sync(build_plan, metadata)


async def apply_async(db, ops: List[Dict[str, Any]], drop_columns: bool = False, metadata=None) -> List[Dict[str, Any]]:
    """Applies safe operations (and drops when allowed); records history."""
    from lila.core.database import Base, _column_ddl

    metadata = metadata or Base.metadata
    applied: List[Dict[str, Any]] = []
    async with db.engine.begin() as conn:
        dialect = conn.dialect
        q = dialect.identifier_preparer.quote
        new_tables = [metadata.tables[op["table"]] for op in ops if op["kind"] == "create_table"]
        if new_tables:
            await conn.run_sync(lambda sc: metadata.create_all(sc, tables=new_tables))
            applied += [op for op in ops if op["kind"] == "create_table"]
        for op in ops:
            kind = op["kind"]
            try:
                if kind == "add_column":
                    column = metadata.tables[op["table"]].columns[op["column"]]
                    ddl = _column_ddl(column, dialect)
                    if not ddl:
                        continue
                    await conn.execute(text(f"ALTER TABLE {q(op['table'])} ADD COLUMN {ddl}"))
                elif kind == "rename_column":
                    await conn.execute(text(
                        f"ALTER TABLE {q(op['table'])} RENAME COLUMN {q(op['old'])} TO {q(op['column'])}"
                    ))
                elif kind == "create_index":
                    index = next(ix for ix in metadata.tables[op["table"]].indexes if ix.name == op["index_name"])
                    await conn.run_sync(lambda sc, ix=index: ix.create(sc))
                elif kind == "drop_column" and drop_columns:
                    await conn.execute(text(f"ALTER TABLE {q(op['table'])} DROP COLUMN {q(op['column'])}"))
                else:
                    continue
                applied.append(op)
            except Exception as exc:
                Logger.error(f"[Lila migrate] {kind} {op['target']} failed: {exc}")
                raise
    await asyncio.to_thread(_record, database_key(db), applied)
    return applied


def discover_and_import_models(extra_modules: Optional[Sequence[str]] = None) -> List[str]:
    """Imports framework/app models from disk (dev) or frozen packages (PyInstaller)."""
    errors: List[str] = []
    try:
        import lila.core.admin  # noqa: F401
    except Exception as exc:
        errors.append(f"lila.core.admin: {exc}")

    candidates: List[str] = []
    models_dir = Path("app/models")
    if models_dir.exists():
        for file in sorted(models_dir.glob("*.py")):
            if file.name != "__init__.py":
                candidates.append(f"app.models.{file.stem}")

    try:
        models_pkg = importlib.import_module("app.models")
        pkg_path = getattr(models_pkg, "__path__", None)
        if pkg_path is not None:
            for mod_info in pkgutil.iter_modules(pkg_path, prefix="app.models."):
                if not mod_info.name.endswith(".__init__"):
                    candidates.append(mod_info.name)
    except ModuleNotFoundError as exc:
        if exc.name not in ("app", "app.models"):
            errors.append(f"app.models: {exc}")
    except Exception as exc:
        errors.append(f"app.models: {exc}")

    env_mods = os.environ.get("LILA_DESKTOP_MODELS", "")
    for item in env_mods.split(","):
        cleaned = item.strip()
        if cleaned:
            candidates.append(cleaned)
    for item in extra_modules or ():
        cleaned = str(item).strip()
        if cleaned:
            candidates.append(cleaned)

    seen = set()
    for module_name in candidates:
        if module_name in seen:
            continue
        seen.add(module_name)
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")
    return errors


def sqlite_db_path(db) -> Optional[str]:
    """Return filesystem path when ``db`` targets a file-backed SQLite database."""
    if db is None or getattr(db, "engine", None) is None:
        return None
    url = db.engine.url
    if not str(url.drivername or "").startswith("sqlite"):
        return None
    raw = str(url.database or "").strip()
    if not raw or raw == ":memory:" or raw.startswith("file::memory:"):
        return None
    return os.path.abspath(raw)


def backup_sqlite_before_migrate(db, max_backups: Optional[int] = None) -> Optional[str]:
    """Create a hot SQLite backup before applying migrations; returns path or None."""
    src_path = sqlite_db_path(db)
    if not src_path or not os.path.isfile(src_path):
        return None
    try:
        if os.path.getsize(src_path) <= 0:
            return None
    except OSError:
        return None

    keep = int(
        ENV_CONFIG.get_int("LILA_MIGRATE_BACKUP_KEEP", 10)
        if max_backups is None
        else max_backups
    )
    backup_dir = get_data_path("backups", "pre_migrate")
    os.makedirs(backup_dir, exist_ok=True)
    stem = Path(src_path).stem or "lila"
    raw_ver = os.environ.get("LILA_APP_VERSION") or str(ENV_CONFIG.get("VERSION_PROJECT", "0") or "0")
    safe_ver = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_ver).strip("_") or "0"
    stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{int((time.time() % 1) * 1_000_000):06d}"
    dst_path = os.path.join(backup_dir, f"pre_migrate_{stem}_v{safe_ver}_{stamp}.sqlite")

    src_conn = sqlite3.connect(src_path)
    dst_conn = sqlite3.connect(dst_path)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    if keep > 0:
        prefix = f"pre_migrate_{stem}_"
        existing = []
        for fname in os.listdir(backup_dir):
            if fname.startswith(prefix) and fname.endswith(".sqlite"):
                cand = os.path.join(backup_dir, fname)
                try:
                    existing.append((os.path.getmtime(cand), cand))
                except OSError:
                    pass
        existing.sort(key=lambda item: item[0])
        while len(existing) > keep:
            _, oldest = existing.pop(0)
            try:
                os.remove(oldest)
            except OSError:
                pass
    return dst_path


def discover_migration_scripts(extra_modules: Optional[Sequence[str]] = None) -> List[str]:
    """Discover ordered versioned Python migration modules (``app/migrations/*.py``)."""
    candidates: List[str] = []
    mig_dir = Path("app/migrations")
    if mig_dir.exists():
        for file in sorted(mig_dir.glob("*.py")):
            if file.name != "__init__.py" and not file.name.startswith("_"):
                candidates.append(f"app.migrations.{file.stem}")

    try:
        mig_pkg = importlib.import_module("app.migrations")
        pkg_path = getattr(mig_pkg, "__path__", None)
        if pkg_path is not None:
            for mod_info in sorted(pkgutil.iter_modules(pkg_path, prefix="app.migrations."), key=lambda m: m.name):
                leaf = mod_info.name.rsplit(".", 1)[-1]
                if not leaf.startswith("_"):
                    candidates.append(mod_info.name)
    except ModuleNotFoundError as exc:
        if exc.name not in ("app", "app.migrations"):
            Logger.warning(f"[Lila migrate] app.migrations import warning: {exc}")
    except Exception as exc:
        Logger.warning(f"[Lila migrate] app.migrations import warning: {exc}")

    env_mods = os.environ.get("LILA_DESKTOP_MIGRATIONS", "")
    for item in env_mods.split(","):
        cleaned = item.strip()
        if cleaned:
            candidates.append(cleaned)
    for item in extra_modules or ():
        cleaned = str(item).strip()
        if cleaned:
            candidates.append(cleaned)

    seen = set()
    ordered: List[str] = []
    for mod in candidates:
        if mod not in seen:
            seen.add(mod)
            ordered.append(mod)
    return sorted(ordered, key=lambda name: (name.rsplit(".", 1)[-1], name))


def applied_scripts(db) -> set[str]:
    conn = _history_conn()
    rows = conn.execute(
        "SELECT name FROM lila_script_migrations WHERE database = ?",
        (database_key(db),),
    ).fetchall()
    return {row[0] for row in rows}


def pending_scripts(db, extra_modules: Optional[Sequence[str]] = None) -> List[str]:
    if not getattr(db, "_connected", False) or getattr(db, "engine", None) is None:
        db.connect()
    done = applied_scripts(db)
    return [mod for mod in discover_migration_scripts(extra_modules=extra_modules) if mod not in done]


async def run_scripts_async(db, extra_modules: Optional[Sequence[str]] = None) -> List[str]:
    """Execute pending versioned ``app/migrations/*.py`` scripts in sorted order."""
    pending = pending_scripts(db, extra_modules=extra_modules)
    if not pending:
        return []
    ran: List[str] = []
    db_key = database_key(db)
    app_ver = str(os.environ.get("LILA_APP_VERSION") or ENV_CONFIG.get("VERSION_PROJECT", "") or "")
    for mod_name in pending:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, "upgrade", None)
        if not callable(fn):
            raise RuntimeError(f"Migration script '{mod_name}' must define callable upgrade(db)")
        res = fn(db)
        if inspect.isawaitable(res):
            await res
        now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

        def _save(name=mod_name, ts=now):
            hist = _history_conn()
            hist.execute(
                "INSERT OR IGNORE INTO lila_script_migrations (database, name, app_version, applied_at) VALUES (?, ?, ?, ?)",
                (db_key, name, app_ver, ts),
            )

        await asyncio.to_thread(_save)
        ran.append(mod_name)
    return ran


def last_auto_migrate_report() -> Dict[str, Any]:
    return {
        "backup_path": _LAST_AUTO_MIGRATE_REPORT.get("backup_path"),
        "applied_ops": list(_LAST_AUTO_MIGRATE_REPORT.get("applied_ops") or []),
        "applied_scripts": list(_LAST_AUTO_MIGRATE_REPORT.get("applied_scripts") or []),
    }


async def auto_migrate_async(
    db=None,
    extra_modules: Optional[Sequence[str]] = None,
    script_modules: Optional[Sequence[str]] = None,
    backup: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Applies safe schema ops + versioned scripts automatically (with pre-backup)."""
    global _LAST_AUTO_MIGRATE_REPORT

    errors = discover_and_import_models(extra_modules=extra_modules)
    for err in errors:
        Logger.warning(f"[Lila auto-migrate] model import warning: {err}")

    if db is None:
        try:
            from app.connections import connection as project_conn

            db = project_conn
        except ModuleNotFoundError:
            from lila.core.database import db as default_conn

            db = default_conn

    if not getattr(db, "_connected", False) or getattr(db, "engine", None) is None:
        db.connect()

    if not getattr(db, "is_async", True):
        db.migrate(use_base=True)
        _LAST_AUTO_MIGRATE_REPORT = {"backup_path": None, "applied_ops": [], "applied_scripts": []}
        return []

    ops = await plan_async(db)
    safe_ops = [op for op in ops if op.get("safe")]
    pending = pending_scripts(db, extra_modules=script_modules)
    if not safe_ops and not pending:
        _LAST_AUTO_MIGRATE_REPORT = {"backup_path": None, "applied_ops": [], "applied_scripts": []}
        return []

    do_backup = ENV_CONFIG.get_bool("LILA_MIGRATE_BACKUP", True) if backup is None else bool(backup)
    backup_path: Optional[str] = None
    if do_backup:
        try:
            backup_path = await asyncio.to_thread(backup_sqlite_before_migrate, db)
            if backup_path:
                Logger.info(f"[Lila auto-migrate] Pre-migration SQLite backup: {backup_path}")
        except Exception as exc:
            Logger.warning(f"[Lila auto-migrate] Pre-migration backup skipped: {exc}")

    applied: List[Dict[str, Any]] = []
    if safe_ops:
        applied = await apply_async(db, safe_ops)
    ran_scripts: List[str] = []
    if pending:
        ran_scripts = await run_scripts_async(db, extra_modules=script_modules)

    _LAST_AUTO_MIGRATE_REPORT = {
        "backup_path": backup_path,
        "applied_ops": applied,
        "applied_scripts": ran_scripts,
    }
    return applied
