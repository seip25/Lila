"""
English: Base Model class for all SQLAlchemy models in Lila Framework.
         Provides common CRUD boilerplate methods, soft-delete configuration,
         dynamic raw SQL execution fallbacks, and foreign-key relation helpers.
Español: Clase BaseModel para todos los modelos SQLAlchemy en Lila Framework.
         Provee boilerplate de CRUD común, configuración de borrado lógico,
         fallbacks de ejecución SQL dinámicos y helpers para relaciones de clave foránea.
"""

from lila.core.database import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import Session, load_only
from app.connections import connection
import asyncio
import datetime
from typing import Type, List, Dict, Any, Optional

# ──────────────────────────────────────────────────────────────────────────────
# English: Query deduplication registry for async SELECT methods.
#          Maps a unique query fingerprint → asyncio.Future.
#          When multiple concurrent async requests ask for the exact same query,
#          only one thread executes against the DB; all others await the same
#          Future. This prevents redundant DB round-trips and respects the
#          connection pool_size configured in Database.
#          Only used for SELECT operations — writes always execute immediately.
# Español: Registro de deduplicación de queries para métodos async SELECT.
#          Mapea una huella única de query → asyncio.Future.
#          Cuando múltiples peticiones async concurrentes piden exactamente la
#          misma query, solo un hilo ejecuta contra la DB; los demás esperan el
#          mismo Future. Esto evita round-trips redundantes y respeta el
#          pool_size del Database.
#          Solo se usa para operaciones SELECT — las escrituras siempre ejecutan.
# ──────────────────────────────────────────────────────────────────────────────
_PENDING_QUERIES: Dict[str, asyncio.Future] = {}

class BaseModel(Base):
    __abstract__ = True
    
    # English: Configuration flags for CRUD and delete behavior.
    #          Subclasses can override these if they don't want soft delete,
    #          use a different active field (e.g. "is_active"), or a different primary key.
    # Español: Flags de configuración para comportamiento CRUD y de borrado.
    #          Las subclases pueden sobreescribir estos si no quieren borrado lógico,
    #          usan un campo activo distinto (ej. "is_active") o una clave primaria distinta.
    _delete_logic = True
    _active_field = "active"
    _primary_key = "id"

    @classmethod
    def get_all(cls, select: str = None, limit: int = 1000, **filters) -> List[Dict[str, Any]]:
        """
        English: Get all records. Supports filtering by columns and selective loading.
        Español: Obtiene todos los registros. Soporta filtrado por columnas y carga selectiva.
        """
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
        """
        English: Non-blocking version of get_all() for use in async Starlette route handlers.
                 Uses asyncio.Future deduplication: if N concurrent requests arrive for the
                 exact same query, only ONE thread hits the database. All other callers
                 await the same Future and receive the result with zero extra DB round-trips.
                 This is safe only for SELECT — use get_all() for write-after-read patterns.
                 Example:
                     @router.get("/products")
                     async def list_products(request):
                         items = await Product.get_all_async(limit=50)
                         return JSONResponse(items)
        Español: Versión no bloqueante de get_all() para usar en rutas async de Starlette.
                 Usa deduplicación de asyncio.Future: si N peticiones concurrentes llegan
                 para la misma query exacta, solo UN hilo toca la base de datos. Los demás
                 esperan el mismo Future y reciben el resultado sin round-trips extra a la DB.
                 Solo seguro para SELECT — usar get_all() para patrones write-after-read.
        """
        cache_key = f"{cls.__tablename__}:get_all:{select}:{limit}:{tuple(sorted(filters.items()))}"
        loop = asyncio.get_running_loop()

        if cache_key in _PENDING_QUERIES:
            # Another coroutine is already fetching this exact data — wait for it.
            return await asyncio.shield(_PENDING_QUERIES[cache_key])

        future: asyncio.Future = loop.create_future()
        _PENDING_QUERIES[cache_key] = future
        try:
            result = await loop.run_in_executor(
                None, lambda: cls.get_all(select=select, limit=limit, **filters)
            )
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            _PENDING_QUERIES.pop(cache_key, None)

    @classmethod
    def get_by_id(cls, db: Session, id: Any) -> Optional[Any]:
        """
        English: Get a record by its primary key ID.
        Español: Obtiene un registro por su ID de clave primaria.
        """
        query = db.query(cls).filter(getattr(cls, cls._primary_key) == id)
        if cls._delete_logic and hasattr(cls, cls._active_field):
            query = query.filter(getattr(cls, cls._active_field) == 1)
        return query.first()

    @classmethod
    async def get_by_id_async(cls, id: Any) -> Optional[Any]:
        """
        English: Non-blocking version of get_by_id() for use in async Starlette route handlers.
                 Uses asyncio.Future deduplication: concurrent requests for the same ID share
                 a single DB round-trip. Opens its own session internally.
                 Example:
                     @router.get("/products/{id}")
                     async def get_product(request):
                         product = await Product.get_by_id_async(request.path_params["id"])
                         return JSONResponse(product or {})
        Español: Versión no bloqueante de get_by_id() para usar en rutas async de Starlette.
                 Usa deduplicación de asyncio.Future: peticiones concurrentes del mismo ID
                 comparten un único round-trip a la DB. Abre su propia sesión internamente.
        """
        cache_key = f"{cls.__tablename__}:get_by_id:{id}"
        loop = asyncio.get_running_loop()

        if cache_key in _PENDING_QUERIES:
            return await asyncio.shield(_PENDING_QUERIES[cache_key])

        future: asyncio.Future = loop.create_future()
        _PENDING_QUERIES[cache_key] = future

        def _fetch():
            db = connection.get_session()
            try:
                return cls.get_by_id(db, id)
            finally:
                db.close()

        try:
            result = await loop.run_in_executor(None, _fetch)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            _PENDING_QUERIES.pop(cache_key, None)

    @classmethod
    def insert(cls, db: Session, params: Dict[str, Any]) -> Any:
        """
        English: Insert a new record into the database.
        Español: Inserta un nuevo registro en la base de datos.
        """
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
    def update(cls, db: Session, id: Any, data: Dict[str, Any]) -> bool:
        """
        English: Update a record by ID.
        Español: Actualiza un registro por ID.
        """
        record = cls.get_by_id(db, id)
        if not record:
            return False
            
        for key, value in data.items():
            if hasattr(record, key):
                setattr(record, key, value)
        db.commit()
        return True

    @classmethod
    def delete(cls, db: Session, id: Any) -> bool:
        """
        English: Delete a record by ID. Performs soft delete if enabled, hard delete otherwise.
        Español: Elimina un registro por ID. Realiza borrado lógico si está habilitado, físico si no.
        """
        record = cls.get_by_id(db, id)
        if not record:
            return False
            
        if cls._delete_logic and hasattr(record, cls._active_field):
            setattr(record, cls._active_field, 0)
        else:
            db.delete(record)
        db.commit()
        return True

    @classmethod
    def get_all_without_orm(cls, select: str = None, limit: int = 1000, **filters) -> List[Dict[str, Any]]:
        """
        English: Fetch records using raw SQL query (without ORM).
        Español: Obtiene registros usando query SQL pura (sin ORM).
        """
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
    def get_by_id_without_orm(cls, id: Any, select: str = None) -> Optional[Dict[str, Any]]:
        """
        English: Fetch a record by ID using raw SQL query (without ORM).
        Español: Obtiene un registro por ID usando query SQL pura (sin ORM).
        """
        if not select:
            select = ", ".join([col.name for col in cls.__table__.columns])
            
        query = f"SELECT {select} FROM {cls.__tablename__} WHERE {cls._primary_key} = :id"
        if cls._delete_logic and hasattr(cls, cls._active_field):
            query += f" AND {cls._active_field} = 1"
        query += " LIMIT 1"
        
        params = {"id": id}
        return connection.query(query=query, params=params, return_row=True)

    def get_related(self, model_class: Type[Any], foreign_key_field: str = None) -> Optional[Any]:
        """
        English: Retrieve related model instance (one-to-one or many-to-one relationship).
        Español: Obtiene la instancia del modelo relacionado (relación uno-a-uno o muchos-a-uno).
        """
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

    def get_related_many(self, model_class: Type[Any], foreign_key_field: str = None, limit: int = 1000) -> List[Any]:
        """
        English: Retrieve related model instances (one-to-many relationship).
        Español: Obtiene las instancias de los modelos relacionados (relación uno-a-muchos).
        """
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
