from lila.core.database import Database
from lila.core.cache import Cache
from lila.core.config import ENV_CONFIG
import os
from dotenv import load_dotenv

load_dotenv()

# Database setup (SQLite async with WAL mode by default)
db_type = ENV_CONFIG.get("DB_TYPE", "sqlite")
db_name = ENV_CONFIG.get("DB_NAME", "lila")

if db_type == "sqlite":
    db_config = {"type": "sqlite", "database": db_name, "is_async": True}
else:
    db_config = {
        "type": db_type,
        "host": ENV_CONFIG.get("DB_HOST", "127.0.0.1"),
        "port": int(ENV_CONFIG.get("DB_PORT", 3306 if db_type == "mysql" else 5432)),
        "user": ENV_CONFIG.get("DB_USER", "root"),
        "password": ENV_CONFIG.get("DB_PASSWORD", ""),
        "database": db_name,
        "is_async": True,
    }

connection = Database(config=db_config)
connection.connect()

# Cache setup (In-Memory by default, or Redis if configured in .env)
cache_driver = ENV_CONFIG.get("CACHE_DRIVER", "memory")
Cache.configure(driver=cache_driver)
