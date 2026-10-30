"""Lila Framework v2.0.x ActiveRecord BaseModel.

Async and sync CRUD, safe single-flight deduplication, cache invalidation and
partial-column serialization that never triggers lazy-load errors.
"""

import asyncio
from typing import Optional, List, Dict, Any, Callable
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import load_only
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


async def run_deduplicated(cache_key: Optional[str], fetch_coro: Callable[[], Any]) -> Any:
    """Runs an async fetch with single-flight deduplication and short TTL caching.

    Cancellation-safe: if one caller disconnects, the shared task keeps running
    for the other waiters instead of leaving them blocked.
    """
    if not cache_key:
        return await fetch_coro()

    cached_res = await Cache.get_async(cache_key)
    if cached_res is not None:
        return cached_res

    existing = _PENDING_QUERIES.get(cache_key)
    if existing is not None and not existing.done():
        return await asyncio.shield(existing)

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
        return await asyncio.shield(task)
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
    def _select_columns(cls, target_select: Optional[str]):
        if not target_select:
            return []
        names = [c.strip() for c in target_select.split(",") if c.strip()]
        cols = []
        unknown = []
        for name in names:
            if hasattr(cls, name):
                cols.append(getattr(cls, name))
            else:
                unknown.append(name)
        if unknown:
            raise ValueError(f"Unknown column(s) for {cls.__name__}: {', '.join(unknown)}")
        return cols

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
            async with conn.transaction() as session:
                from sqlalchemy import select as sa_select

                stmt = sa_select(cls)
                cols = cls._select_columns(target_select)
                if cols:
                    stmt = stmt.options(load_only(*cols))

                if cls._delete_logic and hasattr(cls, cls._active_field):
                    stmt = stmt.where(getattr(cls, cls._active_field) == 1)

                for key, value in filters.items():
                    if hasattr(cls, key):
                        stmt = stmt.where(getattr(cls, key) == value)

                if order_by and hasattr(cls, order_by):
                    order_col = getattr(cls, order_by)
                    stmt = stmt.order_by(order_col.desc() if desc else order_col.asc())

                stmt = stmt.offset(offset).limit(limit)
                result = await session.execute(stmt)
                rows = result.scalars().all()
                return [row.to_dict() for row in rows]

        return await run_deduplicated(cache_key, _fetch)

    @classmethod
    async def get_by_id_async(
        cls, id_val: Any, select_cols: Optional[str] = None, select: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        conn = cls.get_connection()
        target_select = select_cols or select
        cache_key = f"{cls._cache_prefix()}:id:{id_val}:{target_select}"

        async def _fetch():
            async with conn.transaction() as session:
                from sqlalchemy import select as sa_select

                pk_col = getattr(cls, cls._primary_key)
                stmt = sa_select(cls).where(pk_col == id_val)

                if cls._delete_logic and hasattr(cls, cls._active_field):
                    stmt = stmt.where(getattr(cls, cls._active_field) == 1)

                cols = cls._select_columns(target_select)
                if cols:
                    stmt = stmt.options(load_only(*cols))

                result = await session.execute(stmt)
                row = result.scalars().first()
                return row.to_dict() if row else None

        return await run_deduplicated(cache_key, _fetch)

    @classmethod
    async def insert_async(cls, instance: Optional[Any] = None, **values) -> Dict[str, Any]:
        conn = cls.get_connection()
        async with conn.transaction() as session:
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

        async with conn.transaction() as session:
            pk_col = getattr(cls, cls._primary_key)
            stmt = update(cls).where(pk_col == id_val).values(**payload)
            result = await session.execute(stmt)
            updated = result.rowcount > 0

        await cls.invalidate_cache_async()
        return updated

    @classmethod
    async def delete_async(cls, id_val: Any) -> bool:
        conn = cls.get_connection()
        async with conn.transaction() as session:
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
            for key, value in filters.items():
                if hasattr(cls, key):
                    stmt = stmt.where(getattr(cls, key) == value)
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
        **filters,
    ) -> list:
        conn = cls.get_connection()
        if conn.is_async:
            return cls._run_sync(
                cls.get_all_async(select_cols=select_cols or select, limit=limit, offset=offset, **filters)
            )
        with conn.transaction_sync() as session:
            query = session.query(cls)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                query = query.filter(getattr(cls, cls._active_field) == 1)
            for key, value in filters.items():
                if hasattr(cls, key):
                    query = query.filter(getattr(cls, key) == value)
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
            pk_col = getattr(cls, cls._primary_key)
            stmt = update(cls).where(pk_col == id_val).values(**payload)
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
