from lila.core.database import Database
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()

"""
Database connection configurations.

For MySQL async configuration (tuned for low-memory VPS):
config = {
    "type": "mysql",
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "lila_db"),
    "is_async": True,
    "auto_commit": False,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 1800,
    "pool_timeout": 30,
}

For PostgreSQL async configuration:
config = {
    "type": "postgresql",
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "lila_db"),
    "is_async": True,
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 1800,
    "pool_timeout": 30,
}
"""

config = {"type": "sqlite", "database": "lila", "is_async": True}
connection = Database(config=config)
connection.connect()