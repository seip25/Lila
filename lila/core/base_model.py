from lila.core.database import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import Session, load_only
from sqlalchemy.ext.asyncio import AsyncSession
from app.connections import connection
import asyncio
import datetime
from typing import Type, List, Dict, Any, Optional
from lila.core.cache import Cache

_PENDING_QUERIES: Dict[str, asyncio.Future] = {}


async def run_deduplicated(cache_key: Optional[str], sync_func, *args, **kwargs) -> Any:
    """Run a function with query deduplication and Redis caching if available."""
    if cache_key:
        cached_result = await Cache.get_async(cache_key)
        if cached_result is not None:
            return cached_result

        loop = asyncio.get_running_loop()
        if cache_key in _PENDING_QUERIES:
            return await asyncio.shield(_PENDING_QUERIES[cache_key])

        future: asyncio.Future = loop.create_future()
        _PENDING_QUERIES[cache_key] = future
        try:
            if asyncio.iscoroutinefunction(sync_func):
                result = await sync_func(*args, **kwargs)
            else:
                result = await loop.run_in_executor(None, lambda: sync_func(*args, **kwargs))
            
            await Cache.set_async(cache_key, result, ttl=5)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            _PENDING_QUERIES.pop(cache_key, None)
    else:
        loop = asyncio.get_running_loop()
        if asyncio.iscoroutinefunction(sync_func):
            return await sync_func(*args, **kwargs)
        else:
            return await loop.run_in_executor(None, lambda: sync_func(*args, **kwargs))


class BaseModel(Base):
    __abstract__ = True
    _delete_logic = True
    _active_field = "active"
    _primary_key = "id"

    @classmethod
    async def invalidate_cache_async(cls):
        """Invalidate all cached queries for this model in Redis asynchronously."""
        from lila.core.cache import _REDIS_CLIENT_ASYNC
        if _REDIS_CLIENT_ASYNC is not None:
            try:
                keys = await _REDIS_CLIENT_ASYNC.keys(f"model:{cls.__tablename__}:*")
                if keys:
                    await _REDIS_CLIENT_ASYNC.delete(*keys)
            except Exception:
                pass

    @classmethod
    def invalidate_cache(cls):
        """Invalidate all cached queries for this model in Redis synchronously."""
        from lila.core.cache import _REDIS_CLIENT
        if _REDIS_CLIENT is not None:
            try:
                keys = _REDIS_CLIENT.keys(f"model:{cls.__tablename__}:*")
                if keys:
                    _REDIS_CLIENT.delete(*keys)
            except Exception:
                pass

    @classmethod
    async def run_async(cls, cache_key: Optional[str], sync_func, *args, **kwargs) -> Any:
        """Run a synchronous database operation in an executor."""
        return await run_deduplicated(cache_key, sync_func, *args, **kwargs)

    @classmethod
    def get_all(cls, select: str = None, limit: int = 1000, **filters) -> List[Dict[str, Any]]:
        """Get all records synchronously."""
        db = connection.get_session()
        try:
            if select:
                column_names = [c.strip() for c in select.split(',')]
            else:
                column_names = [col.key for col in cls.__table__.columns]
            
            columns_to_load = [getattr(cls, c) for c in column_names if hasattr(cls, c)]
            
            query = db.query(cls)
            if columns_to_load:
                query = query.options(load_only(*columns_to_load))
                
            if cls._delete_logic and hasattr(cls, cls._active_field):
                query = query.filter(getattr(cls, cls._active_field) == 1)
                
            for key, val in filters.items():
                if hasattr(cls, key):
                    query = query.filter(getattr(cls, key) == val)
                    
            result = query.limit(limit).all()
            items = [
                {col: getattr(row, col) for col in column_names if hasattr(row, col)}
                for row in result
            ]
            return items
        finally:
            db.close()

    @classmethod
    async def get_all_async(
        cls,
        select: str = None,
        limit: int = 1000,
        **filters,
    ) -> List[Dict[str, Any]]:
        """Get all records asynchronously."""
        cache_key = f"model:{cls.__tablename__}:get_all:{select}:{limit}:{tuple(sorted(filters.items()))}"

        async def _fetch():
            if not connection.is_async:
                return cls.get_all(select=select, limit=limit, **filters)

            from sqlalchemy import select as sa_select
            async with connection.transaction() as db:
                if select:
                    column_names = [c.strip() for c in select.split(',')]
                else:
                    column_names = [col.key for col in cls.__table__.columns]

                columns_to_load = [getattr(cls, c) for c in column_names if hasattr(cls, c)]

                stmt = sa_select(cls)
                if columns_to_load:
                    stmt = stmt.options(load_only(*columns_to_load))

                if cls._delete_logic and hasattr(cls, cls._active_field):
                    stmt = stmt.where(getattr(cls, cls._active_field) == 1)

                for key, val in filters.items():
                    if hasattr(cls, key):
                        stmt = stmt.where(getattr(cls, key) == val)

                stmt = stmt.limit(limit)
                result = await db.execute(stmt)
                rows = result.scalars().all()
                items = [
                    {col: getattr(row, col) for col in column_names if hasattr(row, col)}
                    for row in rows
                ]
                return items

        return await run_deduplicated(cache_key, _fetch)

    @classmethod
    def get_by_id(cls, db: Session, id: Any) -> Optional[Any]:
        """Get a record by ID synchronously."""
        query = db.query(cls).filter(getattr(cls, cls._primary_key) == id)
        if cls._delete_logic and hasattr(cls, cls._active_field):
            query = query.filter(getattr(cls, cls._active_field) == 1)
        return query.first()

    @classmethod
    async def get_by_id_async(cls, id: Any) -> Optional[Any]:
        """Get a record by ID asynchronously."""
        cache_key = f"model:{cls.__tablename__}:get_by_id:{id}"

        async def _fetch():
            if not connection.is_async:
                db_sess = connection.get_session()
                try:
                    return cls.get_by_id(db_sess, id)
                finally:
                    db_sess.close()

            from sqlalchemy import select as sa_select
            async with connection.transaction() as db:
                stmt = sa_select(cls).where(getattr(cls, cls._primary_key) == id)
                if cls._delete_logic and hasattr(cls, cls._active_field):
                    stmt = stmt.where(getattr(cls, cls._active_field) == 1)
                result = await db.execute(stmt)
                return result.scalars().first()

        return await run_deduplicated(cache_key, _fetch)

    @classmethod
    def insert(cls, db: Session, params: Dict[str, Any]) -> Any:
        """Insert a record synchronously."""
        cls.invalidate_cache()
        valid_params = {}
        for col in cls.__table__.columns:
            if col.name in params:
                valid_params[col.name] = params[col.name]
            elif col.name == cls._active_field and cls._delete_logic:
                valid_params[col.name] = 1
                
        if "created_at" in cls.__table__.columns and "created_at" not in valid_params:
            valid_params["created_at"] = datetime.datetime.now()
            
        instance = cls(**valid_params)
        db.add(instance)
        return instance

    @classmethod
    async def insert_async(cls, db: AsyncSession, params: Dict[str, Any]) -> Any:
        """Insert a record asynchronously."""
        valid_params = {}
        for col in cls.__table__.columns:
            if col.name in params:
                valid_params[col.name] = params[col.name]
            elif col.name == cls._active_field and cls._delete_logic:
                valid_params[col.name] = 1

        if "created_at" in cls.__table__.columns and "created_at" not in valid_params:
            valid_params["created_at"] = datetime.datetime.now()

        instance = cls(**valid_params)
        db.add(instance)
        await db.flush()
        await cls.invalidate_cache_async()
        return instance

    @classmethod
    def update(cls, db: Session, id: Any, data: Dict[str, Any]) -> bool:
        """Update a record synchronously."""
        record = cls.get_by_id(db, id)
        if not record:
            return False
            
        for key, value in data.items():
            if hasattr(record, key):
                setattr(record, key, value)
        db.commit()
        cls.invalidate_cache()
        return True

    @classmethod
    async def update_async(cls, db: AsyncSession, id: Any, data: Dict[str, Any]) -> bool:
        """Update a record asynchronously."""
        from sqlalchemy import select as sa_select
        stmt = sa_select(cls).where(getattr(cls, cls._primary_key) == id)
        if cls._delete_logic and hasattr(cls, cls._active_field):
            stmt = stmt.where(getattr(cls, cls._active_field) == 1)
        result = await db.execute(stmt)
        record = result.scalars().first()
        if not record:
            return False

        for key, value in data.items():
            if hasattr(record, key):
                setattr(record, key, value)
        await db.commit()
        await cls.invalidate_cache_async()
        return True

    @classmethod
    def delete(cls, db: Session, id: Any) -> bool:
        """Delete a record synchronously."""
        record = cls.get_by_id(db, id)
        if not record:
            return False
            
        if cls._delete_logic and hasattr(record, cls._active_field):
            setattr(record, cls._active_field, 0)
        else:
            db.delete(record)
        db.commit()
        cls.invalidate_cache()
        return True

    @classmethod
    async def delete_async(cls, db: AsyncSession, id: Any) -> bool:
        """Delete a record asynchronously."""
        from sqlalchemy import select as sa_select
        stmt = sa_select(cls).where(getattr(cls, cls._primary_key) == id)
        if cls._delete_logic and hasattr(cls, cls._active_field):
            stmt = stmt.where(getattr(cls, cls._active_field) == 1)
        result = await db.execute(stmt)
        record = result.scalars().first()
        if not record:
            return False

        if cls._delete_logic and hasattr(record, cls._active_field):
            setattr(record, cls._active_field, 0)
        else:
            await db.delete(record)
        await db.commit()
        await cls.invalidate_cache_async()
        return True

    @classmethod
    def get_all_without_orm(cls, select: str = None, limit: int = 1000, **filters) -> List[Dict[str, Any]]:
        """Get all records without ORM synchronously."""
        if not select:
            select = ", ".join([col.name for col in cls.__table__.columns])
            
        query = f"SELECT {select} FROM {cls.__tablename__}"
        where_clauses = []
        params = {}
        
        if cls._delete_logic and hasattr(cls, cls._active_field):
            where_clauses.append(f"{cls._active_field} = 1")
            
        for key, val in filters.items():
            where_clauses.append(f"{key} = :{key}")
            params[key] = val
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += f" LIMIT {limit}"
        return connection.query(query=query, params=params, return_rows=True)

    @classmethod
    async def get_all_without_orm_async(cls, select: str = None, limit: int = 1000, **filters) -> List[Dict[str, Any]]:
        """Get all records without ORM asynchronously."""
        if not select:
            select = ", ".join([col.name for col in cls.__table__.columns])
            
        query = f"SELECT {select} FROM {cls.__tablename__}"
        where_clauses = []
        params = {}
        
        if cls._delete_logic and hasattr(cls, cls._active_field):
            where_clauses.append(f"{cls._active_field} = 1")
            
        for key, val in filters.items():
            where_clauses.append(f"{key} = :{key}")
            params[key] = val
            
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            
        query += f" LIMIT {limit}"
        return await connection.query_async(query=query, params=params, return_rows=True)

    @classmethod
    def get_by_id_without_orm(cls, id: Any, select: str = None) -> Optional[Dict[str, Any]]:
        """Get a record by ID without ORM synchronously."""
        if not select:
            select = ", ".join([col.name for col in cls.__table__.columns])
            
        query = f"SELECT {select} FROM {cls.__tablename__} WHERE {cls._primary_key} = :id"
        if cls._delete_logic and hasattr(cls, cls._active_field):
            query += f" AND {cls._active_field} = 1"
        query += " LIMIT 1"
        
        params = {"id": id}
        return connection.query(query=query, params=params, return_row=True)

    @classmethod
    async def get_by_id_without_orm_async(cls, id: Any, select: str = None) -> Optional[Dict[str, Any]]:
        """Get a record by ID without ORM asynchronously."""
        if not select:
            select = ", ".join([col.name for col in cls.__table__.columns])
            
        query = f"SELECT {select} FROM {cls.__tablename__} WHERE {cls._primary_key} = :id"
        if cls._delete_logic and hasattr(cls, cls._active_field):
            query += f" AND {cls._active_field} = 1"
        query += " LIMIT 1"
        
        params = {"id": id}
        return await connection.query_async(query=query, params=params, return_row=True)

    def get_related(self, model_class: Type[Any], foreign_key_field: str = None) -> Optional[Any]:
        """Get a related model instance synchronously."""
        if not foreign_key_field:
            foreign_key_field = f"{model_class.__name__.lower()}_id"
            if not hasattr(self, foreign_key_field):
                foreign_key_field = f"id_{model_class.__name__.lower()}"
                
        fk_val = getattr(self, foreign_key_field, None)
        if fk_val is None:
            return None
            
        db = connection.get_session()
        try:
            related = db.query(model_class).filter(getattr(model_class, model_class._primary_key) == fk_val).first()
            if related and model_class._delete_logic and hasattr(model_class, model_class._active_field):
                if getattr(related, model_class._active_field) != 1:
                    return None
            if related:
                db.expunge(related)
            return related
        finally:
            db.close()

    async def get_related_async(self, model_class: Type[Any], foreign_key_field: str = None) -> Optional[Any]:
        """Get a related model instance asynchronously."""
        if not foreign_key_field:
            foreign_key_field = f"{model_class.__name__.lower()}_id"
            if not hasattr(self, foreign_key_field):
                foreign_key_field = f"id_{model_class.__name__.lower()}"

        fk_val = getattr(self, foreign_key_field, None)
        if fk_val is None:
            return None

        from sqlalchemy import select as sa_select
        async with connection.transaction() as db:
            stmt = sa_select(model_class).where(getattr(model_class, model_class._primary_key) == fk_val)
            if model_class._delete_logic and hasattr(model_class, model_class._active_field):
                stmt = stmt.where(getattr(model_class, model_class._active_field) == 1)
            result = await db.execute(stmt)
            related = result.scalars().first()
            if related:
                db.expunge(related)
            return related

    def get_related_many(self, model_class: Type[Any], foreign_key_field: str = None, limit: int = 1000) -> List[Any]:
        """Get related model instances synchronously."""
        if not foreign_key_field:
            foreign_key_field = f"{self.__class__.__name__.lower()}_id"
            if not hasattr(model_class, foreign_key_field):
                foreign_key_field = f"id_{self.__class__.__name__.lower()}"
                
        pk_val = getattr(self, self._primary_key, None)
        if pk_val is None:
            return []
            
        db = connection.get_session()
        try:
            query = db.query(model_class).filter(getattr(model_class, foreign_key_field) == pk_val)
            if model_class._delete_logic and hasattr(model_class, model_class._active_field):
                query = query.filter(getattr(model_class, model_class._active_field) == 1)
            related_list = query.limit(limit).all()
            for obj in related_list:
                db.expunge(obj)
            return related_list
        finally:
            db.close()

    async def get_related_many_async(self, model_class: Type[Any], foreign_key_field: str = None, limit: int = 1000) -> List[Any]:
        """Get related model instances asynchronously."""
        if not foreign_key_field:
            foreign_key_field = f"{self.__class__.__name__.lower()}_id"
            if not hasattr(model_class, foreign_key_field):
                foreign_key_field = f"id_{self.__class__.__name__.lower()}"

        pk_val = getattr(self, self._primary_key, None)
        if pk_val is None:
            return []

        from sqlalchemy import select as sa_select
        async with connection.transaction() as db:
            stmt = sa_select(model_class).where(getattr(model_class, foreign_key_field) == pk_val)
            if model_class._delete_logic and hasattr(model_class, model_class._active_field):
                stmt = stmt.where(getattr(model_class, model_class._active_field) == 1)
            stmt = stmt.limit(limit)
            result = await db.execute(stmt)
            related_list = result.scalars().all()
            for obj in related_list:
                db.expunge(obj)
            return related_list
