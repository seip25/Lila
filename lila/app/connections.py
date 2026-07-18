from lila.core.database import Database
from sqlalchemy.ext.asyncio import AsyncSession

"""
Database connection configurations.

For PostgreSQL async configuration, use:
config = {
    "type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "password",
    "database": "my_db",
    "is_async": True,
    "pool_size": 20,
    "max_overflow": 40
}

For MySQL async configuration, use:
config = {
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "password",
    "database": "my_db",
    "is_async": True,
    "pool_size": 20,
    "max_overflow": 40
}
"""

config = {"type": "sqlite", "database": "lila", "is_async": True}
connection = Database(config=config)
connection.connect()