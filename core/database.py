from sqlalchemy import create_engine, MetaData, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional
from core.logger import Logger

Base = declarative_base()


class Database:
    def __init__(self, config: dict) -> None:
        self.type = config.get("type", "sqlite")
        self.config = config
        self.connection = None
        self.metadata = MetaData()
        self.tables = []
        self.auto_commit = self.config.get("auto_commit", False)
        self.engine = None
        self.SessionLocal = None

    def connect(self) -> bool:
        if self.type in ["mysql", "postgresql", "psgr"]:
            user = self.config.get("user", "root")
            password = self.config.get("password", "")
            host = self.config.get("host", "127.0.0.1")
            port = self.config.get("port", 3306)
            database = self.config.get("database", "db")
            db_type = "postgresql" if self.type in ["postgresql", "psgr"] else self.type
            connector = "mysqlconnector" if self.type == "mysql" else "psycopg2"
            isolation_level = self.config.get("isolation_level", None)

            temp_engine = create_engine(
                f"{db_type}+{connector}://{user}:{password}@{host}:{port}/postgres"
                if db_type == "postgresql"
                else f"{db_type}+{connector}://{user}:{password}@{host}:{port}/mysql"
            )

            with temp_engine.connect() as connection:
                if db_type == "postgresql":
                    result = connection.execute(
                        text(f"SELECT 1 FROM pg_database WHERE datname = '{database}'")
                    )
                else:  # MySQL
                    result = connection.execute(
                        text(f"SHOW DATABASES LIKE '{database}'")
                    )

                if not result.fetchone():

                    connection.execute(text(f"CREATE DATABASE {database}"))
                    print(f"Database '{database}' created.")

            try:
                self.engine = create_engine(
                    f"{db_type}+{connector}://{user}:{password}@{host}:{port}/{database}",
                    isolation_level=isolation_level,
                    execution_options={"autocommit": self.auto_commit},
                )
                self.SessionLocal = sessionmaker(
                    autocommit=False, autoflush=False, bind=self.engine
                )
            except SQLAlchemyError as e:
                print(f"Database connection error: {e}")
                return False

        else:
            database = self.config.get("database", "db")
            try:
                self.engine = create_engine(f"sqlite:///{database}.sqlite")
                self.SessionLocal = sessionmaker(
                    autocommit=False, autoflush=False, bind=self.engine
                )
            except SQLAlchemyError as e:
                print(f"Create database, error: {e}")
                Logger.error(f"Create database, error: {e}")
                return False
        return True

    def get_session(self) -> Session:
        if not self.SessionLocal:
            raise Exception("Database not connected. Call `connect()` first.")
        return self.SessionLocal()

    def prepare_migrate(self, tables: list) -> None:
        self.tables.extend(tables)

    def migrate(self, use_base: bool = False):
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
    )-> dict | bool | list | None:
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
                    if result:
                        rows = result.fetchall() if result else []
                        items = [dict(getattr(item, "_mapping", {})) for item in rows]
                        return items
                    return []
                if return_row:
                    if result:
                        row = result.fetchone() if result else None
                        if row:
                            item = dict(getattr(row, "_mapping", {}))
                            return item
                    return None
                return result
        except SQLAlchemyError as e:
            print(f"Query error: {e}")
            Logger.error(f"Query error: {e}")
        return result

    def commit(self) -> None:
        if self.connection and not self.auto_commit:
            try:
                self.connection.commit()
            except SQLAlchemyError as e:
                Logger.error(f"Commit error: {e}")
                print(f"Commit error: {e}")

    def close(self) -> None:
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                print("Connection closed.")
            except SQLAlchemyError as e:
                print(f"Close connection error: {e}")
