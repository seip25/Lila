"""Lila Framework v2.0.0 High-Performance Database Engine.
SQLAlchemy 2.0 Async/Sync with SQLite WAL mode by default,
safe driver validation for MySQL/PostgreSQL, transactions, and migration helpers.
"""

import os
import re
from typing import Optional, Any, Union
from contextlib import contextmanager, asynccontextmanager

from sqlalchemy import create_engine, MetaData, text, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from lila.core.config import ENV_CONFIG, get_data_path
from lila.core.logger import Logger


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, config: Optional[dict] = None) -> None:
        if config is None:
            config = {
                "type": ENV_CONFIG.get("DB_TYPE", "sqlite"),
                "database": ENV_CONFIG.get("DB_DATABASE", "lila"),
                "is_async": True,
            }
        self.config = config
        self.type = str(config.get("type", "sqlite")).lower().strip()
        self.is_async = bool(config.get("is_async", True))
        self.metadata = MetaData()
        self.tables: list = []
        self.engine = None
        self.SessionLocal = None
        self._connected: bool = False

    def connect(self) -> bool:
        """Establish database engine and session maker."""
        if self._connected and self.engine is not None:
            return True

        if self.type in ["mysql", "mariadb"]:
            self._connect_mysql()
        elif self.type in ["postgresql", "postgres", "psgr"]:
            self._connect_postgres()
        else:
            self._connect_sqlite()

        self._connected = True
        return True

    def _connect_sqlite(self) -> None:
        raw_db_name = self.config.get("database", "lila")
        if raw_db_name.endswith(".sqlite") or raw_db_name.endswith(".db"):
            db_filename = raw_db_name
        else:
            db_filename = f"{raw_db_name}.sqlite"

        # Store in writable data directory
        db_path = get_data_path(db_filename).replace("\\", "/")

        if self.is_async:
            url = f"sqlite+aiosqlite:///{db_path}"
            self.engine = create_async_engine(url)
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
            target_engine = self.engine.sync_engine
        else:
            url = f"sqlite:///{db_path}"
            self.engine = create_engine(url)
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
            target_engine = self.engine

        # Enable SQLite WAL Mode and performance pragmas
        @event.listens_for(target_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA cache_size=-20000;")
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.execute("PRAGMA temp_store=MEMORY;")
                cursor.close()
            except Exception:
                pass

    def _connect_mysql(self) -> None:
        user = self.config.get("user") or ENV_CONFIG.get("DB_USER", "root")
        password = self.config.get("password") or ENV_CONFIG.get("DB_PASSWORD", "")
        host = self.config.get("host") or ENV_CONFIG.get("DB_HOST", "127.0.0.1")
        port = int(self.config.get("port") or ENV_CONFIG.get("DB_PORT", 3306))
        database = self.config.get("database") or ENV_CONFIG.get("DB_DATABASE", "lila")

        if self.is_async:
            try:
                import aiomysql
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'aiomysql' is required for async MySQL.\n"
                    "Install it using: pip install \"lila-framework[mysql]\""
                )
            connector = "aiomysql"
            url = f"mysql+{connector}://{user}:{password}@{host}:{port}/{database}"
            self.engine = create_async_engine(
                url,
                pool_size=self.config.get("pool_size", 10),
                max_overflow=self.config.get("max_overflow", 20),
                pool_recycle=self.config.get("pool_recycle", 1800),
            )
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        else:
            try:
                import pymysql
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'pymysql' is required for sync MySQL.\n"
                    "Install it using: pip install \"lila-framework[mysql]\""
                )
            connector = "pymysql"
            url = f"mysql+{connector}://{user}:{password}@{host}:{port}/{database}"
            self.engine = create_engine(
                url,
                pool_size=self.config.get("pool_size", 10),
                max_overflow=self.config.get("max_overflow", 20),
                pool_recycle=self.config.get("pool_recycle", 1800),
            )
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )

    def _connect_postgres(self) -> None:
        user = self.config.get("user") or ENV_CONFIG.get("DB_USER", "postgres")
        password = self.config.get("password") or ENV_CONFIG.get("DB_PASSWORD", "")
        host = self.config.get("host") or ENV_CONFIG.get("DB_HOST", "127.0.0.1")
        port = int(self.config.get("port") or ENV_CONFIG.get("DB_PORT", 5432))
        database = self.config.get("database") or ENV_CONFIG.get("DB_DATABASE", "lila")

        if self.is_async:
            try:
                import asyncpg
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'asyncpg' is required for async PostgreSQL.\n"
                    "Install it using: pip install \"lila-framework[postgres]\""
                )
            connector = "asyncpg"
            url = f"postgresql+{connector}://{user}:{password}@{host}:{port}/{database}"
            self.engine = create_async_engine(
                url,
                pool_size=self.config.get("pool_size", 10),
                max_overflow=self.config.get("max_overflow", 20),
            )
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
        else:
            try:
                import psycopg
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'psycopg' is required for sync PostgreSQL.\n"
                    "Install it using: pip install \"lila-framework[postgres]\""
                )
            connector = "psycopg"
            url = f"postgresql+{connector}://{user}:{password}@{host}:{port}/{database}"
            self.engine = create_engine(
                url,
                pool_size=self.config.get("pool_size", 10),
                max_overflow=self.config.get("max_overflow", 20),
            )
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )

    def get_session(self) -> Union[Session, AsyncSession]:
        if not self._connected or self.SessionLocal is None:
            self.connect()
        return self.SessionLocal()

    @asynccontextmanager
    async def transaction(self):
        """Async context manager managing commit/rollback lifecycle."""
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
    def transaction_sync(self):
        """Sync context manager managing commit/rollback lifecycle."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    async def migrate_async(self, use_base: bool = True) -> None:
        """Create tables asynchronously from DeclarativeBase."""
        if not self._connected or self.engine is None:
            self.connect()
        async with self.engine.begin() as conn:
            if use_base:
                await conn.run_sync(Base.metadata.create_all)
            else:
                await conn.run_sync(self.metadata.create_all)

    def migrate(self, use_base: bool = True) -> None:
        """Synchronous migration helper."""
        if not self._connected or self.engine is None:
            self.connect()
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                # schedule task
                loop.create_task(self.migrate_async(use_base))
            else:
                loop.run_until_complete(self.migrate_async(use_base))
        else:
            if use_base:
                Base.metadata.create_all(self.engine)
            else:
                self.metadata.create_all(self.engine)

    async def query_async(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Any:
        """Execute raw SQL query asynchronously."""
        if not self._connected:
            self.connect()
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP")):
                await conn.commit()
            if return_rows:
                rows = result.fetchall()
                return [dict(getattr(r, "_mapping", {})) for r in rows]
            if return_row:
                row = result.fetchone()
                return dict(getattr(row, "_mapping", {})) if row else None
            return result

    def query(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Any:
        """Execute raw SQL query synchronously."""
        if not self._connected:
            self.connect()
        if self.is_async:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_running():
                raise RuntimeError("Use query_async() inside running event loop.")
            return loop.run_until_complete(
                self.query_async(query, params, return_rows=return_rows, return_row=return_row)
            )

        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP")):
                conn.commit()
            if return_rows:
                rows = result.fetchall()
                return [dict(getattr(r, "_mapping", {})) for r in rows]
            if return_row:
                row = result.fetchone()
                return dict(getattr(row, "_mapping", {})) if row else None
            return result

    async def close_async(self) -> None:
        """Closes connections and disposes async engine."""
        if self.engine is not None and self.is_async:
            await self.engine.dispose()
            self._connected = False


# Default database instance
db = Database()
