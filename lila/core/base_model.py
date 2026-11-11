"""Lila Framework v2.0.x ActiveRecord BaseModel.

Async and sync CRUD, safe single-flight deduplication, cache invalidation and
partial-column serialization that never triggers lazy-load errors.
"""

import asyncio
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from lila.core.config import ENV_CONFIG
from lila.core.database import Base, db as default_db
from lila.core.cache import Cache
from lila.core.logger import Logger


# In-flight queries: cache_key -> asyncio.Task (never a bare Future, so a
# cancelled caller cannot leave waiters hanging forever).
_PENDING_QUERIES: Dict[str, "asyncio.Task"] = {}


def _cacheable(value: Any) -> bool:
    return isinstance(value, (dict, list, str, int, float, bool))


def _detached(value: Any) -> Any:
    """Returns a copy of cached rows so callers cannot mutate the shared cache.

    The memory driver stores Python objects by reference; without this, code
    like ``rows[0]["name"] = "x"`` would leak into every other request until
    the TTL expires.
    """
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, dict):
        return dict(value)
    return value


async def run_deduplicated(cache_key: Optional[str], fetch_coro: Callable[[], Any]) -> Any:
    """Runs an async fetch with single-flight deduplication and short TTL caching.

    Cancellation-safe: if one caller disconnects, the shared task keeps running
    for the other waiters instead of leaving them blocked.
    """
    if not cache_key:
        return await fetch_coro()

    cached_res = await Cache.get_async(cache_key)
    if cached_res is not None:
        return _detached(cached_res)

    existing = _PENDING_QUERIES.get(cache_key)
    if existing is not None and not existing.done():
        return _detached(await asyncio.shield(existing))

    ttl = max(1, int(ENV_CONFIG.get("MODEL_CACHE_TTL", 5) or 5))

    async def _runner():
        res = await fetch_coro()
        if _cacheable(res):
            await Cache.set_async(cache_key, res, ttl=ttl)
        return res

    task = asyncio.get_running_loop().create_task(_runner())
    _PENDING_QUERIES[cache_key] = task
    # Consume exceptions if every waiter goes away, to avoid noisy warnings.
    task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
    try:
        return _detached(await asyncio.shield(task))
    finally:
        if _PENDING_QUERIES.get(cache_key) is task:
            _PENDING_QUERIES.pop(cache_key, None)


class BaseModel(Base):
    __abstract__ = True
    _delete_logic: bool = True
    _active_field: str = "active"
    _primary_key: str = "id"
    _connection: Any = None
    # Columns that must never appear in to_dict()/JSON/session payloads.
    __private_fields__: tuple = ()

    @classmethod
    def get_connection(cls):
        if cls._connection is not None:
            return cls._connection
        try:
            from app.connections import connection

            return connection
        except ModuleNotFoundError:
            return default_db
        except Exception as exc:  # configuration/import errors must not silently use another DB
            Logger.error(
                "[Lila Model] Could not import app.connections; refusing to fall back to the "
                f"default database: {exc}",
                exception=exc,
            )
            raise

    def to_dict(self, exclude: Optional[set] = None) -> dict:
        """Converts only loaded columns to primitive values.

        Unloaded columns (``load_only``) are skipped instead of being returned as
        ``None`` or triggering an async lazy-load error.
        """
        exclude = set(exclude or set()) | set(getattr(type(self), "__private_fields__", ()))
        data = {}
        for col in self.__table__.columns:
            if col.name in exclude:
                continue
            if col.name in self.__dict__:
                data[col.name] = self.__dict__[col.name]
        return data

    @staticmethod
    def _write(conn):
        """Write transaction (serialized per process on SQLite when supported)."""
        writer = getattr(conn, "write_transaction", None)
        return writer() if writer is not None else conn.transaction()

    @classmethod
    def _cache_prefix(cls) -> str:
        return f"model:{cls.__tablename__}"

    @classmethod
    async def invalidate_cache_async(cls) -> None:
        await Cache.delete_async(f"{cls._cache_prefix()}:*")

    @classmethod
    def invalidate_cache(cls) -> None:
        Cache.delete(f"{cls._cache_prefix()}:*")

    @classmethod
    def _column(cls, name: str):
        """Returns the mapped column attribute or None (never methods/properties)."""
        if name not in cls.__table__.columns:
            return None
        attr = getattr(cls, name, None)
        return cls.__table__.columns[name] if attr is None else attr

    _FILTER_OPS = {
        "eq": lambda c, v: c == v,
        "ne": lambda c, v: c != v,
        "gt": lambda c, v: c > v,
        "gte": lambda c, v: c >= v,
        "lt": lambda c, v: c < v,
        "lte": lambda c, v: c <= v,
        "in": lambda c, v: c.in_(list(v)),
        "not_in": lambda c, v: c.not_in(list(v)),
        "like": lambda c, v: c.like(v),
        "ilike": lambda c, v: c.ilike(v),
        "contains": lambda c, v: c.ilike(f"%{v}%"),
        "startswith": lambda c, v: c.ilike(f"{v}%"),
        "endswith": lambda c, v: c.ilike(f"%{v}"),
        "isnull": lambda c, v: c.is_(None) if v else c.is_not(None),
    }

    @classmethod
    def _filter_clauses(cls, filters: Dict[str, Any]):
        """``name="x"``, ``price__gte=10``, ``id__in=[1, 2]``, ``email__contains="@gmail"``...

        Unknown columns or operators raise ``ValueError`` (a typo must never
        turn into "return every row").
        """
        clauses = []
        unknown = []
        for key, value in filters.items():
            name, _, op = key.partition("__")
            op = op or "eq"
            col = cls._column(name)
            builder = cls._FILTER_OPS.get(op)
            if col is None or builder is None:
                unknown.append(key)
                continue
            clauses.append(builder(col, value))
        if unknown:
            raise ValueError(f"Unknown filter(s) for {cls.__name__}: {', '.join(unknown)}")
        return clauses

    @classmethod
    def _filter_columns(cls, filters: Dict[str, Any]):
        """Backwards-compatible equality filters as ``(column, value)`` pairs."""
        cols = []
        unknown = []
        for key, value in filters.items():
            col = cls._column(key)
            if col is None:
                unknown.append(key)
            else:
                cols.append((col, value))
        if unknown:
            raise ValueError(f"Unknown filter column(s) for {cls.__name__}: {', '.join(unknown)}")
        return cols

    @classmethod
    def _read_columns(cls, target_select: Optional[str]):
        """Table columns to read: the requested ones, or all non-private columns."""
        private = set(getattr(cls, "__private_fields__", ()) or ())
        if target_select:
            cols = cls._select_columns(target_select)
            return [cls.__table__.columns[c.key] if hasattr(c, "key") and c.key in cls.__table__.columns else c
                    for c in cols if getattr(c, "key", None) not in private]
        return [c for c in cls.__table__.columns if c.name not in private]

    @classmethod
    def _read_stmt(cls, target_select=None, filters=None, order_by=None, desc=False):
        """Core SELECT returning plain rows: no ORM objects, no lazy loads,
        private columns never leave the database."""
        from sqlalchemy import select as sa_select

        stmt = sa_select(*cls._read_columns(target_select))
        if cls._delete_logic and cls._column(cls._active_field) is not None:
            stmt = stmt.where(getattr(cls, cls._active_field) == 1)
        for clause in cls._filter_clauses(filters or {}):
            stmt = stmt.where(clause)
        order_col = cls._column(order_by) if order_by else None
        if order_by and order_col is None:
            raise ValueError(f"Unknown order_by column for {cls.__name__}: {order_by}")
        if order_col is not None:
            stmt = stmt.order_by(order_col.desc() if desc else order_col.asc())
        return stmt

    @classmethod
    def _select_columns(cls, target_select: Optional[str]):
        if not target_select:
            return []
        names = [c.strip() for c in target_select.split(",") if c.strip()]
        cols = []
        unknown = []
        for name in names:
            col = cls._column(name)
            if col is not None:
                cols.append(col)
            else:
                unknown.append(name)
        if unknown:
            raise ValueError(f"Unknown column(s) for {cls.__name__}: {', '.join(unknown)}")
        return cols

    @classmethod
    def _update_stmt(cls, id_val: Any, payload: dict):
        """UPDATE ... WHERE pk = id, skipping soft-deleted rows.

        Soft-deleted rows can still be restored explicitly by including the
        active field in the payload (e.g. ``update_async(id, active=1)``).
        """
        pk_col = getattr(cls, cls._primary_key)
        stmt = update(cls).where(pk_col == id_val)
        if (
            cls._delete_logic
            and cls._column(cls._active_field) is not None
            and cls._active_field not in payload
        ):
            stmt = stmt.where(getattr(cls, cls._active_field) == 1)
        return stmt.values(**payload)

    # ──────────────────────────────────────────────────────────────────────────
    # Async CRUD
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    async def get_all_async(
        cls,
        select_cols: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
        select: Optional[str] = None,
        order_by: Optional[str] = None,
        desc: bool = False,
        **filters,
    ) -> List[Dict[str, Any]]:
        conn = cls.get_connection()
        target_select = select_cols or select
        cache_key = (
            f"{cls._cache_prefix()}:all:{target_select}:{limit}:{offset}:{order_by}:{desc}:"
            f"{tuple(sorted(filters.items()))}"
        )

        async def _fetch():
            stmt = cls._read_stmt(target_select, filters, order_by, desc).offset(offset).limit(limit)
            async with conn.transaction() as session:
                result = await session.execute(stmt)
                return [dict(row) for row in result.mappings().all()]

        return await run_deduplicated(cache_key, _fetch)

    @classmethod
    async def paginate_async(
        cls,
        page: int = 1,
        per_page: int = 20,
        order_by: Optional[str] = None,
        desc: bool = False,
        select: Optional[str] = None,
        max_per_page: int = 100,
        **filters,
    ) -> Dict[str, Any]:
        """One call for list pages and APIs::

            page = await Product.paginate_async(page=2, per_page=20, order_by="name", price__gte=10)
            # {"items": [...], "page": 2, "per_page": 20, "total": 134, "pages": 7,
            #  "has_prev": True, "has_next": True, "prev_page": 1, "next_page": 3}

        Render links with ``{{ pagination(page) }}`` in Jinja.
        """
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        try:
            per_page = max(1, min(int(per_page), int(max_per_page)))
        except (TypeError, ValueError):
            per_page = 20
        total = await cls.count_async(**filters)
        pages = max(1, -(-total // per_page))
        page = min(page, pages)
        items = await cls.get_all_async(
            select=select, limit=per_page, offset=(page - 1) * per_page,
            order_by=order_by, desc=desc, **filters,
        )
        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_prev": page > 1,
            "has_next": page < pages,
            "prev_page": page - 1 if page > 1 else None,
            "next_page": page + 1 if page < pages else None,
        }

    @classmethod
    async def get_by_id_async(
        cls, id_val: Any, select_cols: Optional[str] = None, select: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        conn = cls.get_connection()
        target_select = select_cols or select
        cache_key = f"{cls._cache_prefix()}:id:{id_val}:{target_select}"

        async def _fetch():
            pk_col = getattr(cls, cls._primary_key)
            stmt = cls._read_stmt(target_select).where(pk_col == id_val).limit(1)
            async with conn.transaction() as session:
                result = await session.execute(stmt)
                row = result.mappings().first()
                return dict(row) if row else None

        return await run_deduplicated(cache_key, _fetch)

    @classmethod
    async def insert_async(cls, instance: Optional[Any] = None, **values) -> Dict[str, Any]:
        conn = cls.get_connection()
        async with cls._write(conn) as session:
            record = instance if instance is not None else cls(**values)
            session.add(record)
            await session.flush()
            data = record.to_dict()
        await cls.invalidate_cache_async()
        return data

    @classmethod
    async def update_async(
        cls, id_val: Any, values: Optional[dict] = None, **kwargs
    ) -> bool:
        conn = cls.get_connection()
        payload = dict(values or {})
        payload.update(kwargs)
        if not payload:
            return False

        async with cls._write(conn) as session:
            stmt = cls._update_stmt(id_val, payload)
            result = await session.execute(stmt)
            updated = result.rowcount > 0

        await cls.invalidate_cache_async()
        return updated

    @classmethod
    async def delete_async(cls, id_val: Any) -> bool:
        conn = cls.get_connection()
        async with cls._write(conn) as session:
            pk_col = getattr(cls, cls._primary_key)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                stmt = update(cls).where(pk_col == id_val).values({getattr(cls, cls._active_field): 0})
            else:
                stmt = delete(cls).where(pk_col == id_val)
            result = await session.execute(stmt)
            deleted = result.rowcount > 0

        await cls.invalidate_cache_async()
        return deleted

    @classmethod
    async def count_async(cls, **filters) -> int:
        conn = cls.get_connection()
        async with conn.transaction() as session:
            pk_col = getattr(cls, cls._primary_key)
            stmt = select(func.count(pk_col))
            if cls._delete_logic and hasattr(cls, cls._active_field):
                stmt = stmt.where(getattr(cls, cls._active_field) == 1)
            for clause in cls._filter_clauses(filters):
                stmt = stmt.where(clause)
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ──────────────────────────────────────────────────────────────────────────
    # Sync compatibility helpers
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _run_sync(cls, coro):
        conn = cls.get_connection()
        return conn.run_sync(coro)

    @classmethod
    def get_all(
        cls,
        select_cols: Optional[str] = None,
        limit: int = 1000,
        select: Optional[str] = None,
        offset: int = 0,
        order_by: Optional[str] = None,
        desc: bool = False,
        **filters,
    ) -> list:
        conn = cls.get_connection()
        if conn.is_async:
            return cls._run_sync(
                cls.get_all_async(
                    select_cols=select_cols or select,
                    limit=limit,
                    offset=offset,
                    order_by=order_by,
                    desc=desc,
                    **filters,
                )
            )
        with conn.transaction_sync() as session:
            query = session.query(cls)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                query = query.filter(getattr(cls, cls._active_field) == 1)
            for clause in cls._filter_clauses(filters):
                query = query.filter(clause)
            order_col = cls._column(order_by) if order_by else None
            if order_col is not None:
                query = query.order_by(order_col.desc() if desc else order_col.asc())
            rows = query.offset(offset).limit(limit).all()
            return [row.to_dict() for row in rows]

    @classmethod
    def get_by_id(cls, id_val: Any) -> Optional[dict]:
        conn = cls.get_connection()
        if conn.is_async:
            return cls._run_sync(cls.get_by_id_async(id_val))
        with conn.transaction_sync() as session:
            pk_col = getattr(cls, cls._primary_key)
            query = session.query(cls).filter(pk_col == id_val)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                query = query.filter(getattr(cls, cls._active_field) == 1)
            row = query.first()
            return row.to_dict() if row else None

    @classmethod
    def insert(cls, instance: Optional[Any] = None, **values) -> dict:
        conn = cls.get_connection()
        if conn.is_async:
            return cls._run_sync(cls.insert_async(instance, **values))
        with conn.transaction_sync() as session:
            record = instance if instance is not None else cls(**values)
            session.add(record)
            session.flush()
            data = record.to_dict()
        cls.invalidate_cache()
        return data

    @classmethod
    def update(cls, id_val: Any, values: Optional[dict] = None, **kwargs) -> bool:
        conn = cls.get_connection()
        if conn.is_async:
            return cls._run_sync(cls.update_async(id_val, values, **kwargs))
        payload = dict(values or {})
        payload.update(kwargs)
        if not payload:
            return False
        with conn.transaction_sync() as session:
            stmt = cls._update_stmt(id_val, payload)
            res = session.execute(stmt)
            ok = res.rowcount > 0
        cls.invalidate_cache()
        return ok

    @classmethod
    def delete(cls, id_val: Any) -> bool:
        conn = cls.get_connection()
        if conn.is_async:
            return cls._run_sync(cls.delete_async(id_val))
        with conn.transaction_sync() as session:
            pk_col = getattr(cls, cls._primary_key)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                stmt = update(cls).where(pk_col == id_val).values({getattr(cls, cls._active_field): 0})
            else:
                stmt = delete(cls).where(pk_col == id_val)
            res = session.execute(stmt)
            ok = res.rowcount > 0
        cls.invalidate_cache()
        return ok
