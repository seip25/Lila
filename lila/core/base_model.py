"""Lila Framework v2.0.0 ActiveRecord BaseModel.
Async & Sync CRUD operations, automatic dict serialization,
Single-Flight deduplication, and cache invalidation.
"""

import asyncio
from typing import Optional, List, Dict, Any, Union, Type
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import load_only
from lila.core.database import Base, db as default_db
from lila.core.cache import Cache

_PENDING_QUERIES: Dict[str, asyncio.Future] = {}


async def run_deduplicated(cache_key: Optional[str], fetch_coro) -> Any:
    """Run an async fetch with single-flight deduplication and short TTL caching."""
    if not cache_key:
        return await fetch_coro()

    cached_res = await Cache.get_async(cache_key)
    if cached_res is not None:
        return cached_res

    loop = asyncio.get_running_loop()
    if cache_key in _PENDING_QUERIES:
        return await asyncio.shield(_PENDING_QUERIES[cache_key])

    future: asyncio.Future = loop.create_future()
    _PENDING_QUERIES[cache_key] = future
    try:
        res = await fetch_coro()
        # Only cache serializable dict/list/primitives, not raw SQLAlchemy instances
        if isinstance(res, (dict, list, str, int, float, bool)) or res is None:
            await Cache.set_async(cache_key, res, ttl=5)
        future.set_result(res)
        return res
    except Exception as exc:
        future.set_exception(exc)
        raise
    finally:
        _PENDING_QUERIES.pop(cache_key, None)


class BaseModel(Base):
    __abstract__ = True
    _delete_logic: bool = True
    _active_field: str = "active"
    _primary_key: str = "id"
    _connection: Any = None

    @classmethod
    def get_connection(cls):
        if cls._connection is not None:
            return cls._connection
        try:
            from app.connections import connection
            return connection
        except Exception:
            return default_db

    def to_dict(self, exclude: Optional[set] = None) -> dict:
        """Converts model instance to primitive dict."""
        exclude = exclude or set()
        data = {}
        for col in self.__table__.columns:
            if col.name not in exclude:
                val = getattr(self, col.name)
                data[col.name] = val
        return data

    @classmethod
    async def invalidate_cache_async(cls) -> None:
        """Invalidates cached queries for this model in memory and redis."""
        Cache.delete(f"model:{cls.__tablename__}:*")
        try:
            r = await Cache._get_redis_async()
            if r is not None:
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor=cursor, match=f"lila:cache:model:{cls.__tablename__}:*", count=100)
                    if keys:
                        await r.delete(*keys)
                    if cursor == 0:
                        break
        except Exception:
            pass

    @classmethod
    def invalidate_cache(cls) -> None:
        """Synchronously invalidates cached queries for this model."""
        Cache.delete(f"model:{cls.__tablename__}:*")
        try:
            r = Cache._get_redis_sync()
            if r is not None:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor=cursor, match=f"lila:cache:model:{cls.__tablename__}:*", count=100)
                    if keys:
                        r.delete(*keys)
                    if cursor == 0:
                        break
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # Async CRUD Operations
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    async def get_all_async(
        cls,
        select_cols: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
        select: Optional[str] = None,
        **filters,
    ) -> List[Dict[str, Any]]:
        conn = cls.get_connection()
        target_select = select_cols or select
        cache_key = (
            f"model:{cls.__tablename__}:all:{target_select}:{limit}:{offset}:"
            f"{tuple(sorted(filters.items()))}"
        )

        async def _fetch():
            async with conn.transaction() as session:
                from sqlalchemy import select as sa_select
                stmt = sa_select(cls)
                if target_select:
                    col_names = [c.strip() for c in target_select.split(",") if c.strip()]
                    cols = [getattr(cls, c) for c in col_names if hasattr(cls, c)]
                    if cols:
                        stmt = stmt.options(load_only(*cols))

                if cls._delete_logic and hasattr(cls, cls._active_field):
                    stmt = stmt.where(getattr(cls, cls._active_field) == 1)

                for k, v in filters.items():
                    if hasattr(cls, k):
                        stmt = stmt.where(getattr(cls, k) == v)

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
        cache_key = f"model:{cls.__tablename__}:id:{id_val}:{target_select}"

        async def _fetch():
            async with conn.transaction() as session:
                from sqlalchemy import select as sa_select
                pk_col = getattr(cls, cls._primary_key)
                stmt = sa_select(cls).where(pk_col == id_val)

                if cls._delete_logic and hasattr(cls, cls._active_field):
                    stmt = stmt.where(getattr(cls, cls._active_field) == 1)

                if target_select:
                    col_names = [c.strip() for c in target_select.split(",") if c.strip()]
                    cols = [getattr(cls, c) for c in col_names if hasattr(cls, c)]
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
            if instance is not None:
                record = instance
            else:
                record = cls(**values)
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
                stmt = update(cls).where(pk_col == id_val).values({cls._active_field: 0})
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
            for k, v in filters.items():
                if hasattr(cls, k):
                    stmt = stmt.where(getattr(cls, k) == v)
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ──────────────────────────────────────────────────────────────────────────
    # Synchronous CRUD Helpers
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def get_all(cls, select_cols: Optional[str] = None, limit: int = 1000, select: Optional[str] = None, **filters) -> list:
        conn = cls.get_connection()
        if conn.is_async:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(cls.get_all_async(select_cols=select_cols or select, limit=limit, **filters))
        with conn.transaction_sync() as session:
            query = session.query(cls)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                query = query.filter(getattr(cls, cls._active_field) == 1)
            for k, v in filters.items():
                if hasattr(cls, k):
                    query = query.filter(getattr(cls, k) == v)
            rows = query.limit(limit).all()
            return [row.to_dict() for row in rows]

    @classmethod
    def get_by_id(cls, id_val: Any) -> Optional[dict]:
        conn = cls.get_connection()
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
        payload = dict(values or {})
        payload.update(kwargs)
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
        with conn.transaction_sync() as session:
            pk_col = getattr(cls, cls._primary_key)
            if cls._delete_logic and hasattr(cls, cls._active_field):
                stmt = update(cls).where(pk_col == id_val).values({cls._active_field: 0})
            else:
                stmt = delete(cls).where(pk_col == id_val)
            res = session.execute(stmt)
            ok = res.rowcount > 0
        cls.invalidate_cache()
        return ok
