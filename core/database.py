from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from sqlalchemy import select, update, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional,Type,Dict,Any
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
        self.auto_commit=self.config.get("auto_commit", False)
        self.auto_flush=self.config.get("auto_flush", False)

    def connect(self) -> bool:
        if self.type in ["mysql", "postgresql", "psgr"]:
            user = self.config.get("user", "root")
            password = self.config.get("password", "")
            host = self.config.get("host", "127.0.0.1")
            port = self.config.get("port", 3306)
            database = self.config.get("database", "db")
            db_type = "postgresql" if self.type in ["postgresql", "psgr"] else self.type
            connector = "mysqlconnector" if self.type == "mysql" else "psycopg"
            isolation_level = self.config.get("isolation_level", None)
 
            temp_engine = create_engine(
                f"{db_type}+{connector}://{user}:{password}@{host}:{port}/postgres"
                if db_type == "postgresql"
                else f"{db_type}+{connector}://{user}:{password}@{host}:{port}/mysql"
            )

            with temp_engine.connect() as connection:
                if db_type == "postgresql":
                    connection = connection.execution_options(isolation_level="AUTOCOMMIT")
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
                    autocommit=self.auto_commit, autoflush=self.auto_flush, bind=self.engine
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
                if self.type in ["postgresql", "psgr"]:
                    if query.strip().upper().startswith(("INSERT")):
                        if result:
                           result.lastrowid = result.fetchone()[0]
                        return result
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

 
    def query_orm(
        self,
        model: Type[Any],
        operation: str= "select",
        instance: Optional[Any] = None,
        session: Optional[Session] = None,
        filters: Optional[Dict[str, Any]] = None,
        values: Optional[Dict[str, Any]] = None,
        return_one: bool = False
    ):
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