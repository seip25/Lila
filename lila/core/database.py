"""Lila Framework v2.0.x Database Engine.

SQLAlchemy 2.0 async/sync with SQLite WAL mode by default, safe driver
validation, transactions, raw queries and a lightweight schema sync that adds
missing columns (``lila migrate`` no longer reports success while the app is
one column behind).
"""

import os
import re
import asyncio
from typing import Optional, Any, Union, Dict, List
from contextlib import contextmanager, asynccontextmanager

from sqlalchemy import create_engine, MetaData, text, event, inspect as sa_inspect
from sqlalchemy.engine import URL
from sqlalchemy.schema import CreateColumn
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from lila.core.config import ENV_CONFIG, get_data_path
from lila.core.logger import Logger


_WRITE_SQL = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|TRUNCATE|VACUUM|ATTACH|DETACH|PRAGMA)\b",
    re.IGNORECASE,
)


class Base(DeclarativeBase):
    pass


def _scalar_default(column) -> Any:
    default = getattr(column, "default", None)
    if default is None:
        return None
    value = getattr(default, "arg", None)
    if callable(value):
        return None
    return value


def _column_ddl(column, dialect) -> Optional[str]:
    """Compiles an ALTER TABLE ADD COLUMN definition, including scalar defaults."""
    default_value = _scalar_default(column)
    try:
        sql = str(CreateColumn(column).compile(dialect=dialect))
    except Exception:
        return None
    if "DEFAULT" not in sql.upper() and default_value is not None:
        if isinstance(default_value, bool):
            literal = "1" if default_value else "0"
        elif isinstance(default_value, (int, float)):
            literal = str(default_value)
        elif isinstance(default_value, str):
            literal = "'" + default_value.replace("'", "''") + "'"
        else:
            literal = None
        if literal is not None:
            sql += f" DEFAULT {literal}"
    return sql


class Database:
    def __init__(self, config: Optional[dict] = None) -> None:
        self._explicit_config = config is not None
        if config is None:
            # Resolved lazily in connect() so App()/ConfigLoader can load .env first.
            config = {"type": "sqlite", "database": "lila", "is_async": True}
        self.config = config
        self.type = str(config.get("type", "sqlite")).lower().strip()
        self.is_async = bool(config.get("is_async", True))
        self.metadata = MetaData()
        self.tables: list = []
        self.engine = None
        self.SessionLocal = None
        self._connected: bool = False
        self._sync_loop = None

    def _resolve_default_config(self) -> None:
        if self._explicit_config:
            return
        db_type = str(ENV_CONFIG.get("DB_TYPE", "sqlite")).lower().strip()
        self.type = db_type
        self.config = {
            "type": db_type,
            "database": ENV_CONFIG.get("DB_NAME", ENV_CONFIG.get("DB_DATABASE", "lila")),
            "is_async": True,
        }
        self.is_async = True

    def run_sync(self, coro):
        """Runs an async DB coroutine from sync code on a persistent loop.

        The loop is reused because asyncio DB drivers bind pooled connections to
        the loop that created them. Calling ``asyncio.run`` repeatedly would
        leave the pool pointing at closed loops.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Use the *_async variants inside an event loop.")

        if self._sync_loop is None or self._sync_loop.is_closed():
            self._sync_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._sync_loop)
        return self._sync_loop.run_until_complete(coro)

    # --------------------------------------------------------------------------
    # Connection management
    # --------------------------------------------------------------------------
    def connect(self) -> bool:
        """Establish the database engine and session maker."""
        if self._connected and self.engine is not None:
            return True

        self._resolve_default_config()

        if self.type in ("mysql", "mariadb"):
            self._connect_mysql()
        elif self.type in ("postgresql", "postgres", "psgr"):
            self._connect_postgres()
        else:
            self._connect_sqlite()

        self._connected = True
        return True

    def _connect_sqlite(self) -> None:
        raw_db_name = str(self.config.get("database") or "lila")
        if raw_db_name.endswith((".sqlite", ".sqlite3", ".db")):
            db_filename = raw_db_name
        else:
            db_filename = f"{raw_db_name}.sqlite"

        db_path = get_data_path(db_filename).replace("\\", "/")
        try:
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        except Exception:
            pass

        connect_args = {"timeout": 30}
        pool_kwargs = {}
        if self.is_async:
            url = f"sqlite+aiosqlite:///{db_path}"
            self.engine = create_async_engine(
                url,
                connect_args=connect_args,
                pool_pre_ping=True,
                pool_size=int(self.config.get("pool_size", 5)),
                max_overflow=int(self.config.get("max_overflow", 10)),
            )
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                autoflush=False,
                expire_on_commit=False,
            )
            target_engine = self.engine.sync_engine
        else:
            url = f"sqlite:///{db_path}"
            self.engine = create_engine(
                url,
                connect_args=connect_args,
                pool_pre_ping=True,
                **pool_kwargs,
            )
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autoflush=False,
            )
            target_engine = self.engine

        @event.listens_for(target_engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                pragmas = (
                    "PRAGMA journal_mode=WAL;",
                    "PRAGMA synchronous=NORMAL;",
                    "PRAGMA busy_timeout=5000;",
                    "PRAGMA cache_size=-4000;",
                    "PRAGMA foreign_keys=ON;",
                    "PRAGMA temp_store=MEMORY;",
                    "PRAGMA mmap_size=67108864;",
                    "PRAGMA journal_size_limit=67108864;",
                    "PRAGMA wal_autocheckpoint=1000;",
                )
                for statement in pragmas:
                    try:
                        cursor.execute(statement)
                    except Exception:
                        pass
                cursor.close()
            except Exception:
                pass

    def _build_url(self, drivername: str, default_user: str, default_port: int) -> URL:
        user = self.config.get("user") or ENV_CONFIG.get("DB_USER", default_user)
        password = self.config.get("password") or ENV_CONFIG.get("DB_PASSWORD", "")
        host = self.config.get("host") or ENV_CONFIG.get("DB_HOST", "127.0.0.1")
        raw_port = self.config.get("port") or ENV_CONFIG.get("DB_PORT", 0)
        try:
            port = int(raw_port) or default_port
        except (TypeError, ValueError):
            port = default_port
        database = self.config.get("database") or ENV_CONFIG.get(
            "DB_NAME", ENV_CONFIG.get("DB_DATABASE", "lila")
        )
        return URL.create(
            drivername=drivername,
            username=str(user) if user else None,
            password=str(password) if password else None,
            host=str(host),
            port=port,
            database=str(database),
        )

    def _connect_mysql(self) -> None:
        if self.is_async:
            try:
                import aiomysql  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'aiomysql' is required for async MySQL.\n"
                    "Install it using: pip install \"lila-framework[mysql]\""
                )
            url = self._build_url("mysql+aiomysql", "root", 3306)
            self.engine = create_async_engine(
                url,
                pool_size=int(self.config.get("pool_size", 10)),
                max_overflow=int(self.config.get("max_overflow", 20)),
                pool_recycle=int(self.config.get("pool_recycle", 1800)),
                pool_pre_ping=True,
            )
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                autoflush=False,
                expire_on_commit=False,
            )
        else:
            try:
                import pymysql  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'pymysql' is required for sync MySQL.\n"
                    "Install it using: pip install \"lila-framework[mysql]\""
                )
            url = self._build_url("mysql+pymysql", "root", 3306)
            self.engine = create_engine(
                url,
                pool_size=int(self.config.get("pool_size", 10)),
                max_overflow=int(self.config.get("max_overflow", 20)),
                pool_recycle=int(self.config.get("pool_recycle", 1800)),
                pool_pre_ping=True,
            )
            self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False)

    def _connect_postgres(self) -> None:
        if self.is_async:
            try:
                import asyncpg  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'asyncpg' is required for async PostgreSQL.\n"
                    "Install it using: pip install \"lila-framework[postgres]\""
                )
            url = self._build_url("postgresql+asyncpg", "postgres", 5432)
            self.engine = create_async_engine(
                url,
                pool_size=int(self.config.get("pool_size", 10)),
                max_overflow=int(self.config.get("max_overflow", 20)),
                pool_pre_ping=True,
            )
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                autoflush=False,
                expire_on_commit=False,
            )
        else:
            try:
                import psycopg  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    "[Lila Database] Package 'psycopg' is required for sync PostgreSQL.\n"
                    "Install it using: pip install \"lila-framework[postgres]\""
                )
            url = self._build_url("postgresql+psycopg", "postgres", 5432)
            self.engine = create_engine(
                url,
                pool_size=int(self.config.get("pool_size", 10)),
                max_overflow=int(self.config.get("max_overflow", 20)),
                pool_pre_ping=True,
            )
            self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False)

    def get_session(self) -> Union[Session, AsyncSession]:
        if not self._connected or self.SessionLocal is None:
            self.connect()
        return self.SessionLocal()

    # --------------------------------------------------------------------------
    # Transactions
    # --------------------------------------------------------------------------
    @asynccontextmanager
    async def transaction(self):
        """Async context manager managing commit/rollback lifecycle."""
        session = self.get_session()
        if not isinstance(session, AsyncSession):
            raise RuntimeError("transaction() requires an async database; use transaction_sync().")
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        finally:
            await session.close()

    @contextmanager
    def transaction_sync(self):
        """Sync context manager managing commit/rollback lifecycle."""
        session = self.get_session()
        if isinstance(session, AsyncSession):
            raise RuntimeError("transaction_sync() cannot be used with an async database; use transaction().")
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            raise exc
        finally:
            session.close()

    # --------------------------------------------------------------------------
    # Migrations / schema sync
    # --------------------------------------------------------------------------
    async def migrate_async(self, use_base: bool = True, add_columns: bool = True) -> Dict[str, Any]:
        """Creates missing tables and (by default) adds missing columns."""
        if not self._connected or self.engine is None:
            self.connect()
        metadata = Base.metadata if use_base else self.metadata
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            report = {"tables": sorted(metadata.tables.keys()), "added_columns": []}
            if add_columns:
                report["added_columns"] = await self._sync_columns_async(conn, metadata)
        return report

    async def _sync_columns_async(self, conn, metadata) -> List[str]:
        added: List[str] = []

        def _collect(sync_conn):
            inspector = sa_inspect(sync_conn)
            existing_tables = set(inspector.get_table_names())
            dialect = sync_conn.dialect
            pending = []
            for table in metadata.sorted_tables:
                if table.name not in existing_tables:
                    continue
                existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name in existing_cols:
                        continue
                    if column.primary_key:
                        continue
                    # SQLite/MySQL cannot add NOT NULL columns without a scalar default.
                    if (
                        not column.nullable
                        and column.server_default is None
                        and _scalar_default(column) is None
                    ):
                        pending.append((table, column, "skipped_not_null"))
                        continue
                    pending.append((table, column, None))
            return pending, dialect

        pending, dialect = await conn.run_sync(_collect)
        preparer = dialect.identifier_preparer
        for table, column, skip_reason in pending:
            if skip_reason:
                Logger.warning(
                    f"[Lila migrate] Skipped non-null column '{table.name}.{column.name}' "
                    "without a default; add it manually or provide a server_default."
                )
                continue
            try:
                column_sql = _column_ddl(column, dialect)
                if not column_sql:
                    continue
                table_sql = preparer.quote(table.name)
                await conn.execute(text(f"ALTER TABLE {table_sql} ADD COLUMN {column_sql}"))
                added.append(f"{table.name}.{column.name}")
            except Exception as exc:
                Logger.error(f"[Lila migrate] Could not add column {table.name}.{column.name}: {exc}")
        return added

    def migrate(self, use_base: bool = True) -> None:
        """Synchronous migration helper (safe to call outside a running loop)."""
        if not self._connected or self.engine is None:
            self.connect()

        if self.is_async:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                self.run_sync(self.migrate_async(use_base))
                return
            raise RuntimeError(
                "migrate() cannot run inside an active event loop. Use 'await db.migrate_async()'."
            )

        metadata = Base.metadata if use_base else self.metadata
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            # Best effort for sync engines: reuse the same inspection logic.
            inspector = sa_inspect(conn)
            dialect = conn.dialect
            existing_tables = set(inspector.get_table_names())
            preparer = dialect.identifier_preparer
            for table in metadata.sorted_tables:
                if table.name not in existing_tables:
                    continue
                existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name in existing_cols or column.primary_key:
                        continue
                    if (
                        not column.nullable
                        and column.server_default is None
                        and _scalar_default(column) is None
                    ):
                        continue
                    try:
                        column_sql = _column_ddl(column, dialect)
                        if not column_sql:
                            continue
                        conn.execute(text(f"ALTER TABLE {preparer.quote(table.name)} ADD COLUMN {column_sql}"))
                    except Exception as exc:
                        Logger.error(f"[Lila migrate] Could not add {table.name}.{column.name}: {exc}")

    async def drop_all_async(self, use_base: bool = True) -> None:
        if not self._connected or self.engine is None:
            self.connect()
        metadata = Base.metadata if use_base else self.metadata
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.drop_all)

    def drop_all(self, use_base: bool = True) -> None:
        if not self._connected or self.engine is None:
            self.connect()
        metadata = Base.metadata if use_base else self.metadata
        if self.is_async:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                self.run_sync(self.drop_all_async(use_base))
                return
            raise RuntimeError("drop_all() cannot run inside an active event loop. Use 'await db.drop_all_async()'.")
        metadata.drop_all(self.engine)

    # --------------------------------------------------------------------------
    # Raw queries
    # --------------------------------------------------------------------------
    async def query_async(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Any:
        """Execute raw SQL asynchronously. Returns rows as dicts when requested."""
        if not self._connected:
            self.connect()
        is_write = bool(_WRITE_SQL.match(query))
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            rows = None
            row = None
            if return_rows and getattr(result, "returns_rows", False):
                rows = result.fetchall()
            elif return_row and getattr(result, "returns_rows", False):
                row = result.fetchone()
            if is_write or not getattr(result, "returns_rows", False):
                await conn.commit()
            if return_rows:
                return [dict(getattr(r, "_mapping", {})) for r in (rows or [])]
            if return_row:
                return dict(getattr(row, "_mapping", {})) if row else None
            return result

    def query(
        self,
        query: str,
        params: Optional[dict] = None,
        return_rows: bool = False,
        return_row: bool = False,
    ) -> Any:
        """Execute raw SQL synchronously."""
        if not self._connected:
            self.connect()
        if self.is_async:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return self.run_sync(
                    self.query_async(query, params, return_rows=return_rows, return_row=return_row)
                )
            raise RuntimeError("Use query_async() inside a running event loop.")

        is_write = bool(_WRITE_SQL.match(query))
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            rows = result.fetchall() if (return_rows and getattr(result, "returns_rows", False)) else None
            row = result.fetchone() if (return_row and getattr(result, "returns_rows", False)) else None
            if is_write or not getattr(result, "returns_rows", False):
                conn.commit()
            if return_rows:
                return [dict(getattr(r, "_mapping", {})) for r in (rows or [])]
            if return_row:
                return dict(getattr(row, "_mapping", {})) if row else None
            return result

    async def close_async(self) -> None:
        """Closes connections and disposes async/sync engines."""
        try:
            if self.engine is not None:
                if self.is_async:
                    await self.engine.dispose()
                elif hasattr(self.engine, "dispose"):
                    self.engine.dispose()
        finally:
            self._connected = False
            self.SessionLocal = None
            if self._sync_loop is not None and not self._sync_loop.is_closed():
                try:
                    self._sync_loop.close()
                except Exception:
                    pass
                self._sync_loop = None


# Default database instance (lazy: no connection is opened until used).
db = Database()
