from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import Optional, Type, Dict, Any, Union
from lila.core.logger import Logger
import re
from contextlib import contextmanager, asynccontextmanager


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, config: dict) -> None:
        """Initialize database configuration settings."""
        self.type = config.get("type", "sqlite")
        self.config = config
        self.connection = None
        self.metadata = MetaData()
        self.tables = []
        self.engine = None
        self.SessionLocal = None
        self.is_async = self.config.get("is_async", True)
        self.auto_commit = self.config.get("auto_commit", False)
        self.auto_flush = self.config.get("auto_flush", False)

    def connect(self) -> bool:
        """Establish database engine and session maker."""
        if self.type in ["mysql", "postgresql", "psgr"]:
            user = self.config.get("user", "root")
            password = self.config.get("password", "")
            host = self.config.get("host", "127.0.0.1")
            port = self.config.get("port", 5432 if self.type in ["postgresql", "psgr"] else 3306)
            database = self.config.get("database", "db")
            db_type = "postgresql" if self.type in ["postgresql", "psgr"] else self.type
            
            if self.is_async:
                connector = "asyncpg" if db_type == "postgresql" else "aiomysql"
            else:
                connector = "psycopg" if db_type == "postgresql" else "mysqlconnector"
                
            isolation_level = self.config.get("isolation_level", None)
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', database):
                Logger.error(f"Invalid database name: {database}")
                return False

            if self.is_async:
                async def _check_and_create_db():
                    temp_url = (
                        f"{db_type}+{connector}://{user}:{password}@{host}:{port}/postgres"
                        if db_type == "postgresql"
                        else f"{db_type}+{connector}://{user}:{password}@{host}:{port}/mysql"
                    )
                    temp_engine = create_async_engine(temp_url)
                    try:
                        async with temp_engine.connect() as conn:
                            if db_type == "postgresql":
                                conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
                                result = await conn.execute(
                                    text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                                    {"dbname": database}
                                )
                            else:
                                conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
                                result = await conn.execute(
                                    text("SHOW DATABASES LIKE :dbname"),
                                    {"dbname": database}
                                )
                            if not result.fetchone():
                                await conn.execute(text(f"CREATE DATABASE {database}"))
                                print(f"Database '{database}' created.")
                    finally:
                        await temp_engine.dispose()

                try:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    if loop.is_running():
                        loop.create_task(_check_and_create_db())
                    else:
                        loop.run_until_complete(_check_and_create_db())
                except Exception as e:
                    Logger.warning(f"Database creation check skipped: {e}")
            else:
                temp_engine = create_engine(
                    f"{db_type}+{connector}://{user}:{password}@{host}:{port}/postgres"
                    if db_type == "postgresql"
                    else f"{db_type}+{connector}://{user}:{password}@{host}:{port}/mysql"
                )
                with temp_engine.connect() as conn:
                    if db_type == "postgresql":
                        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                        result = conn.execute(
                            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                            {"dbname": database}
                        )
                    else:
                        result = conn.execute(
                            text("SHOW DATABASES LIKE :dbname"),
                            {"dbname": database}
                        )
                    if not result.fetchone():
                        conn.execute(text(f"CREATE DATABASE {database}"))
                        print(f"Database '{database}' created.")
                temp_engine.dispose()

            try:
                pool_size = self.config.get("pool_size", 20)
                max_overflow = self.config.get("max_overflow", 40)
                pool_recycle = self.config.get("pool_recycle", 1800)
                pool_timeout = self.config.get("pool_timeout", 30)
                
                if self.is_async:
                    self.engine = create_async_engine(
                        f"{db_type}+{connector}://{user}:{password}@{host}:{port}/{database}",
                        isolation_level=isolation_level,
                        pool_size=pool_size,
                        max_overflow=max_overflow,
                        pool_recycle=pool_recycle,
                        pool_timeout=pool_timeout,
                    )
                    self.SessionLocal = async_sessionmaker(
                        autocommit=False, autoflush=self.auto_flush, bind=self.engine, expire_on_commit=False
                    )
                else:
                    self.engine = create_engine(
                        f"{db_type}+{connector}://{user}:{password}@{host}:{port}/{database}",
                        isolation_level=isolation_level,
                        execution_options={"autocommit": self.auto_commit},
                        pool_size=pool_size,
                        max_overflow=max_overflow,
                        pool_recycle=pool_recycle,
                        pool_timeout=pool_timeout,
                    )
                    self.SessionLocal = sessionmaker(
                        autocommit=False, autoflush=self.auto_flush, bind=self.engine
                    )
            except ImportError as e:
                print(f"Database driver import error: {e}")
                return False
            except SQLAlchemyError as e:
                print(f"Database connection error: {e}")
                return False
        else:
            database = self.config.get("database", "db")
            try:
                if self.is_async:
                    self.engine = create_async_engine(f"sqlite+aiosqlite:///{database}.sqlite")
                    self.SessionLocal = async_sessionmaker(
                        autocommit=False, autoflush=False, bind=self.engine, expire_on_commit=False
                    )
                else:
                    self.engine = create_engine(f"sqlite:///{database}.sqlite")
                    self.SessionLocal = sessionmaker(
                        autocommit=False, autoflush=False, bind=self.engine
                    )
            except SQLAlchemyError as e:
                print(f"Create database, error: {e}")
                Logger.error(f"Create database, error: {e}")
                return False
        return True

    def get_session(self) -> Union[Session, AsyncSession]:
        """Retrieve a session from the session maker."""
        if not self.SessionLocal:
            raise Exception("Database not connected. Call connect() first.")
        return self.SessionLocal()

    @asynccontextmanager
    async def transaction(self) -> AsyncSession:
        """Context manager to handle an async database session transaction with automatic commit/rollback."""
        session = self.get_session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

    @contextmanager
    def transaction_sync(self) -> Session:
        """Context manager to handle a sync database session transaction with automatic commit/rollback."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def prepare_migrate(self, tables: list) -> None:
        """Prepare tables for migration."""
        self.tables.extend(tables)

    async def migrate_async(self, use_base: bool = False):
        """Run database migrations asynchronously."""
        async with self.engine.begin() as conn:
            if use_base:
                await conn.run_sync(Base.metadata.create_all)
            else:
                await conn.run_sync(self.metadata.create_all)

    def migrate(self, use_base: bool = False):
        """Run database migrations synchronously."""
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                raise RuntimeError("Cannot call synchronous migrate() in a running event loop. Use migrate_async() instead.")
            loop.run_until_complete(self.migrate_async(use_base))
            print("success migrations")
        else:
            try:
                if use_base:
                    Base.metadata.create_all(self.engine)
                else:
                    self.metadata.create_all(self.engine)
                print("success migrations")
            except SQLAlchemyError as e:
                Logger.error(f"Error database.py: {e}")
                print(e)


    def query(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Union[dict, bool, list, None]:
        """Execute a raw SQL query synchronously."""
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                raise RuntimeError("Cannot call synchronous query() in a running event loop. Use query_async() instead.")
            return loop.run_until_complete(self._query_async_native(query, params, return_rows, return_row))

        result = False
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(query), params or ())
                if (
                    query.strip()
                    .upper()
                    .startswith(("CREATE", "INSERT", "UPDATE", "DELETE"))
                ):
                    connection.commit()
                if return_rows:
                    rows = result.fetchall()
                    items = [dict(getattr(item, "_mapping", {})) for item in rows]
                    return items
                if return_row:
                    row = result.fetchone()
                    if row:
                        return dict(getattr(row, "_mapping", {}))
                    return None
                if self.type in ["postgresql", "psgr"]:
                    if query.strip().upper().startswith("INSERT"):
                        if result:
                            result.lastrowid = result.fetchone()[0]
                        return result
                return result
        except SQLAlchemyError as e:
            print(f"Query error: {e}")
            Logger.error(f"Query error: {e}")
        return result

    async def _query_async_native(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Any:
        """Execute a raw SQL query asynchronously using the async engine."""
        async with self.engine.connect() as connection:
            result = await connection.execute(text(query), params or ())
            if (
                query.strip()
                .upper()
                .startswith(("CREATE", "INSERT", "UPDATE", "DELETE"))
            ):
                await connection.commit()
            if return_rows:
                rows = result.fetchall()
                items = [dict(getattr(item, "_mapping", {})) for item in rows]
                return items
            if return_row:
                row = result.fetchone()
                if row:
                    return dict(getattr(row, "_mapping", {}))
                return None
            return result

    async def query_async(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Any:
        """Execute a raw SQL query asynchronously with query deduplication."""
        import asyncio
        from lila.core.base_model import _PENDING_QUERIES

        is_select = query.strip().upper().startswith("SELECT")

        if is_select:
            params_tuple = tuple(sorted(params.items())) if params else ()
            cache_key = f"db_query:{query}:{params_tuple}:{return_rows}:{return_row}"

            if cache_key in _PENDING_QUERIES:
                return await asyncio.shield(_PENDING_QUERIES[cache_key])

            loop = asyncio.get_running_loop()
            future: asyncio.Future = loop.create_future()
            _PENDING_QUERIES[cache_key] = future
            try:
                if self.is_async:
                    result = await self._query_async_native(query, params, return_rows, return_row)
                else:
                    result = await loop.run_in_executor(
                        None, lambda: self.query(query, params, return_rows, return_row)
                    )
                future.set_result(result)
                return result
            except Exception as exc:
                future.set_exception(exc)
                raise
            finally:
                _PENDING_QUERIES.pop(cache_key, None)
        else:
            if self.is_async:
                return await self._query_async_native(query, params, return_rows, return_row)
            else:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, lambda: self.query(query, params, return_rows, return_row)
                )

    def commit(self) -> None:
        """Commit the current synchronous transaction."""
        if self.connection and not self.auto_commit:
            try:
                self.connection.commit()
            except SQLAlchemyError as e:
                Logger.error(f"Commit error: {e}")
                print(f"Commit error: {e}")

    def close(self) -> None:
        """Close the current database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                print("Connection closed.")
            except SQLAlchemyError as e:
                print(f"Close connection error: {e}")

    def check_connection(self) -> bool:
        """Check database connectivity."""
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            async def _check():
                async with self.engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                return True
                
            try:
                if loop.is_running():
                    return True
                return loop.run_until_complete(_check())
            except Exception:
                return False
        else:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            except Exception:
                return False

    async def drop_all_async(self, use_base: bool = False):
        """Drop all tables asynchronously."""
        async with self.engine.begin() as conn:
            if self.type == "mysql":
                await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            if use_base:
                await conn.run_sync(Base.metadata.drop_all)
            else:
                await conn.run_sync(self.metadata.drop_all)
            if self.type == "mysql":
                await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

    def drop_all(self, use_base: bool = False):
        """Drop all tables synchronously."""
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                raise RuntimeError("Cannot call synchronous drop_all() in a running event loop. Use drop_all_async() instead.")
            loop.run_until_complete(self.drop_all_async(use_base))
        else:
            with self.engine.begin() as conn:
                if self.type == "mysql":
                    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                if use_base:
                    Base.metadata.drop_all(conn)
                else:
                    self.metadata.drop_all(conn)
                if self.type == "mysql":
                    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))


    async def query_orm_async(
        self,
        model: Type[Any],
        operation: str = "select",
        instance: Optional[Any] = None,
        session: Optional[AsyncSession] = None,
        filters: Optional[Dict[str, Any]] = None,
        values: Optional[Dict[str, Any]] = None,
        return_one: bool = False
    ) -> Any:
        """Execute ORM database operations asynchronously."""
        own_session = False
        if session is None:
            session = self.get_session()
            own_session = True

        try:
            if operation == "insert":
                if not instance:
                    raise ValueError("Instance required for insert")
                session.add(instance)
                await session.commit()
                await session.refresh(instance)
                return instance.id  

            elif operation == "select":
                stmt = select(model)
                if filters:
                    for k, v in filters.items():
                        stmt = stmt.where(getattr(model, k) == v)
                result = await session.execute(stmt)
                results = result.scalars()
                return results.first() if return_one else results.all()

            elif operation == "update":
                if not values:
                    raise ValueError("Values required for update")
                stmt = update(model)
                if filters:
                    for k, v in filters.items():
                        stmt = stmt.where(getattr(model, k) == v)
                stmt = stmt.values(**values)
                await session.execute(stmt)
                await session.commit()
                return True

            elif operation == "delete":
                stmt = delete(model)
                if filters:
                    for k, v in filters.items():
                        stmt = stmt.where(getattr(model, k) == v)
                await session.execute(stmt)
                await session.commit()
                return True

            else:
                raise ValueError(f"Unsupported operation: {operation}")

        except IntegrityError as e:
            await session.rollback()
            print(f"ORM Integrity error: {e}")
            Logger.warning(f"ORM Integrity error: {e}")
            return 0   

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"ORM general error: {e}")
            Logger.error(f"ORM general error: {e}")
            return 0

        finally:
            if own_session:
                await session.close()

    def query_orm(
        self,
        model: Type[Any],
        operation: str = "select",
        instance: Optional[Any] = None,
        session: Optional[Session] = None,
        filters: Optional[Dict[str, Any]] = None,
        values: Optional[Dict[str, Any]] = None,
        return_one: bool = False
    ) -> Any:
        """Execute ORM database operations synchronously."""
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                raise RuntimeError("Cannot call synchronous query_orm() in a running event loop. Use query_orm_async() instead.")
            return loop.run_until_complete(
                self.query_orm_async(
                    model=model,
                    operation=operation,
                    instance=instance,
                    session=session,
                    filters=filters,
                    values=values,
                    return_one=return_one
                )
            )

        own_session = False
        if session is None:
            session = self.get_session()
            own_session = True

        try:
            if operation == "insert":
                if not instance:
                    raise ValueError("Instance required for insert")
                session.add(instance)
                session.commit()
                session.refresh(instance)
                return instance.id  

            elif operation == "select":
                stmt = select(model)
                if filters:
                    for k, v in filters.items():
                        stmt = stmt.where(getattr(model, k) == v)
                results = session.execute(stmt).scalars()
                return results.first() if return_one else results.all()

            elif operation == "update":
                if not values:
                    raise ValueError("Values required for update")
                stmt = update(model)
                if filters:
                    for k, v in filters.items():
                        stmt = stmt.where(getattr(model, k) == v)
                stmt = stmt.values(**values)
                session.execute(stmt)
                session.commit()
                return True

            elif operation == "delete":
                stmt = delete(model)
                if filters:
                    for k, v in filters.items():
                        stmt = stmt.where(getattr(model, k) == v)
                session.execute(stmt)
                session.commit()
                return True

            else:
                raise ValueError(f"Unsupported operation: {operation}")

        except IntegrityError as e:
            session.rollback()
            print(f"ORM Integrity error: {e}")
            Logger.warning(f"ORM Integrity error: {e}")
            return 0   

        except SQLAlchemyError as e:
            session.rollback()
            print(f"ORM general error: {e}")
            Logger.error(f"ORM general error: {e}")
            return 0

        finally:
            if own_session:
                session.close()