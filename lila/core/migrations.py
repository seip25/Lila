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
(``lila migrate history``), never in the project database.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect as sa_inspect, text

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
"""


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


def _record(database: str, applied: List[Dict[str, Any]]) -> None:
    if not applied:
        return
    from lila.core import system_db

    conn = system_db.connect("lila_system", _HISTORY_SCHEMA)
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO lila_migrations (applied_at, database, kind, target, detail) VALUES (?, ?, ?, ?, ?)",
        [(now, database, op["kind"], op["target"], op["detail"]) for op in applied],
    )


def history(limit: int = 50) -> List[Dict[str, Any]]:
    from lila.core import system_db

    conn = system_db.connect("lila_system", _HISTORY_SCHEMA)
    rows = conn.execute(
        "SELECT applied_at, database, kind, target, detail FROM lila_migrations ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]


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
    url = db.engine.url
    database = f"{url.get_backend_name()}:{url.database or ''}"
    await asyncio.to_thread(_record, database, applied)
    return applied
