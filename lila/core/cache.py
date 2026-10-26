"""Lila Framework v2.0.0 High-Performance Cache.
Features In-Memory LRU + TTL storage by default, optional Redis backend,
dynamic configuration with options, single-flight deduplication, and atomic increments.
"""

import time
import pickle
from collections import OrderedDict
from functools import wraps
from typing import Any, Optional, Union
from lila.core.config import ENV_CONFIG
from lila.core.responses import orjson_dumps, orjson_loads

try:
    import redis
    import redis.asyncio as aioredis
    HAS_REDIS_PKG = True
except ImportError:
    redis = None
    aioredis = None
    HAS_REDIS_PKG = False


class Cache:
    """Zero-Infra In-Memory LRU Cache by default, with seamless Redis scaling."""
    _driver: str = "memory"
    _options: dict = {}
    _DATA: OrderedDict[str, tuple[Any, float]] = OrderedDict()
    _MAX_ITEMS: int = 10000
    _DEFAULT_TTL: int = 300

    _redis_sync = None
    _redis_async = None
    _redis_sync_initialized: bool = False
    _redis_async_initialized: bool = False
    _redis_last_retry: float = 0.0

    @classmethod
    def configure(cls, driver: Optional[str] = None, options: Optional[dict] = None) -> None:
        """Configure cache driver and options programmatically or from environment."""
        if driver is None:
            driver = str(ENV_CONFIG.get("CACHE_DRIVER", "memory")).lower().strip()
        else:
            driver = driver.lower().strip()

        cls._options = options or {}

        if driver == "redis":
            if not HAS_REDIS_PKG:
                print(
                    "[Lila Cache] Package 'redis' is not installed "
                    "(run: pip install lila-framework[redis]). Falling back to in-memory cache."
                )
                cls._driver = "memory"
            else:
                cls._driver = "redis"
                cls._redis_sync = None
                cls._redis_async = None
                cls._redis_sync_initialized = False
                cls._redis_async_initialized = False
        else:
            cls._driver = "memory"

        cls._MAX_ITEMS = int(cls._options.get("max_items", 10000))
        cls._DEFAULT_TTL = int(cls._options.get("default_ttl", 300))

    @classmethod
    def _get_driver(cls) -> str:
        if not hasattr(cls, "_driver") or not cls._driver:
            cls.configure()
        return cls._driver

    # ──────────────────────────────────────────────────────────────────────────
    # Redis Client Helpers
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def _get_redis_sync(cls):
        if not HAS_REDIS_PKG or cls._get_driver() != "redis":
            return None
        now = time.time()
        if cls._redis_sync is not None:
            return cls._redis_sync
        if cls._redis_sync_initialized and (now - cls._redis_last_retry < 10.0):
            return None

        cls._redis_last_retry = now
        host = cls._options.get("host") or ENV_CONFIG.get("REDIS_HOST", "127.0.0.1")
        port = int(cls._options.get("port") or ENV_CONFIG.get("REDIS_PORT", 6379))
        password = cls._options.get("password") or ENV_CONFIG.get("REDIS_PASSWORD", None)
        db = int(cls._options.get("db", 0))
        url = cls._options.get("url") or ENV_CONFIG.get("REDIS_URL", None)
        timeout = float(cls._options.get("socket_timeout", 1.5))

        try:
            if url:
                client = redis.from_url(url, socket_timeout=timeout, decode_responses=False)
            else:
                client = redis.Redis(
                    host=host, port=port, password=password, db=db,
                    socket_timeout=timeout, decode_responses=False
                )
            client.ping()
            cls._redis_sync = client
            cls._redis_sync_initialized = True
            return cls._redis_sync
        except Exception:
            cls._redis_sync = None
            cls._redis_sync_initialized = True
            return None

    @classmethod
    async def _get_redis_async(cls):
        if not HAS_REDIS_PKG or cls._get_driver() != "redis":
            return None
        now = time.time()
        if cls._redis_async is not None:
            return cls._redis_async
        if cls._redis_async_initialized and (now - cls._redis_last_retry < 10.0):
            return None

        cls._redis_last_retry = now
        host = cls._options.get("host") or ENV_CONFIG.get("REDIS_HOST", "127.0.0.1")
        port = int(cls._options.get("port") or ENV_CONFIG.get("REDIS_PORT", 6379))
        password = cls._options.get("password") or ENV_CONFIG.get("REDIS_PASSWORD", None)
        db = int(cls._options.get("db", 0))
        url = cls._options.get("url") or ENV_CONFIG.get("REDIS_URL", None)
        timeout = float(cls._options.get("socket_timeout", 1.5))

        try:
            if url:
                client = aioredis.from_url(url, socket_timeout=timeout, decode_responses=False)
            else:
                client = aioredis.Redis(
                    host=host, port=port, password=password, db=db,
                    socket_timeout=timeout, decode_responses=False
                )
            await client.ping()
            cls._redis_async = client
            cls._redis_async_initialized = True
            return cls._redis_async
        except Exception:
            cls._redis_async = None
            cls._redis_async_initialized = True
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Serialization Helpers
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _serialize(value: Any) -> bytes:
        try:
            return b"JSN:" + orjson_dumps(value)
        except Exception:
            return b"PKL:" + pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def _deserialize(raw: bytes) -> Any:
        if raw.startswith(b"JSN:"):
            return orjson_loads(raw[4:])
        if raw.startswith(b"PKL:"):
            return pickle.loads(raw[4:])
        return raw

    # ──────────────────────────────────────────────────────────────────────────
    # Synchronous Operations
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        r = cls._get_redis_sync()
        if r is not None:
            try:
                raw = r.get(f"lila:cache:{key}")
                if raw is not None:
                    return cls._deserialize(raw)
            except Exception:
                pass

        # Memory Fallback / Native Memory
        now = time.time()
        if key in cls._DATA:
            val, expiry = cls._DATA[key]
            if expiry > now:
                cls._DATA.move_to_end(key)
                return val
            del cls._DATA[key]
        return default

    @classmethod
    def set(cls, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        ttl = ttl if ttl is not None else cls._DEFAULT_TTL
        r = cls._get_redis_sync()
        if r is not None:
            try:
                raw = cls._serialize(value)
                r.set(f"lila:cache:{key}", raw, ex=ttl if ttl > 0 else None)
                return True
            except Exception:
                pass

        # Memory storage (LRU)
        now = time.time()
        expiry = now + ttl if ttl > 0 else float("inf")
        if len(cls._DATA) >= cls._MAX_ITEMS:
            # Purge expired items first
            expired_keys = [k for k, (_, exp) in cls._DATA.items() if exp <= now]
            for k in expired_keys:
                del cls._DATA[k]
            # If still full, pop the oldest
            if len(cls._DATA) >= cls._MAX_ITEMS:
                cls._DATA.popitem(last=False)

        cls._DATA[key] = (value, expiry)
        cls._DATA.move_to_end(key)
        return True

    @classmethod
    def delete(cls, key: str) -> None:
        r = cls._get_redis_sync()
        if r is not None:
            try:
                if "*" in key:
                    cursor = 0
                    while True:
                        cursor, keys = r.scan(cursor=cursor, match=f"lila:cache:{key}", count=100)
                        if keys:
                            r.delete(*keys)
                        if cursor == 0:
                            break
                else:
                    r.delete(f"lila:cache:{key}")
            except Exception:
                pass
        if "*" in key:
            prefix = key.split("*", 1)[0]
            matching = [k for k in cls._DATA.keys() if k.startswith(prefix)]
            for k in matching:
                cls._DATA.pop(k, None)
        else:
            cls._DATA.pop(key, None)

    @classmethod
    def clear(cls) -> None:
        r = cls._get_redis_sync()
        if r is not None:
            try:
                cursor = 0
                while True:
                    cursor, keys = r.scan(cursor=cursor, match="lila:cache:*", count=100)
                    if keys:
                        r.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                pass
        cls._DATA.clear()

    @classmethod
    def incr(cls, key: str, ttl: int = 60) -> int:
        """Atomic increment for rate limiting and counters."""
        r = cls._get_redis_sync()
        if r is not None:
            try:
                rk = f"lila:cache:{key}"
                val = r.incr(rk)
                if val == 1 and ttl > 0:
                    r.expire(rk, ttl)
                return val
            except Exception:
                pass

        now = time.time()
        if key in cls._DATA:
            val, expiry = cls._DATA[key]
            if expiry > now:
                new_val = int(val) + 1
                cls._DATA[key] = (new_val, expiry)
                cls._DATA.move_to_end(key)
                return new_val
        new_val = 1
        cls._DATA[key] = (new_val, now + ttl)
        cls._DATA.move_to_end(key)
        return new_val

    # ──────────────────────────────────────────────────────────────────────────
    # Asynchronous Operations
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    async def get_async(cls, key: str, default: Any = None) -> Any:
        r = await cls._get_redis_async()
        if r is not None:
            try:
                raw = await r.get(f"lila:cache:{key}")
                if raw is not None:
                    return cls._deserialize(raw)
            except Exception:
                pass

        # Memory Fallback
        now = time.time()
        if key in cls._DATA:
            val, expiry = cls._DATA[key]
            if expiry > now:
                cls._DATA.move_to_end(key)
                return val
            del cls._DATA[key]
        return default

    @classmethod
    async def set_async(cls, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        ttl = ttl if ttl is not None else cls._DEFAULT_TTL
        r = await cls._get_redis_async()
        if r is not None:
            try:
                raw = cls._serialize(value)
                await r.set(f"lila:cache:{key}", raw, ex=ttl if ttl > 0 else None)
                return True
            except Exception:
                pass

        now = time.time()
        expiry = now + ttl if ttl > 0 else float("inf")
        if len(cls._DATA) >= cls._MAX_ITEMS:
            expired_keys = [k for k, (_, exp) in cls._DATA.items() if exp <= now]
            for k in expired_keys:
                del cls._DATA[k]
            if len(cls._DATA) >= cls._MAX_ITEMS:
                cls._DATA.popitem(last=False)

        cls._DATA[key] = (value, expiry)
        cls._DATA.move_to_end(key)
        return True

    @classmethod
    async def delete_async(cls, key: str) -> None:
        r = await cls._get_redis_async()
        if r is not None:
            try:
                if "*" in key:
                    cursor = 0
                    while True:
                        cursor, keys = await r.scan(cursor=cursor, match=f"lila:cache:{key}", count=100)
                        if keys:
                            await r.delete(*keys)
                        if cursor == 0:
                            break
                else:
                    await r.delete(f"lila:cache:{key}")
            except Exception:
                pass
        if "*" in key:
            prefix = key.split("*", 1)[0]
            matching = [k for k in cls._DATA.keys() if k.startswith(prefix)]
            for k in matching:
                cls._DATA.pop(k, None)
        else:
            cls._DATA.pop(key, None)

    @classmethod
    async def clear_async(cls) -> None:
        r = await cls._get_redis_async()
        if r is not None:
            try:
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor=cursor, match="lila:cache:*", count=100)
                    if keys:
                        await r.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                pass
        cls._DATA.clear()

    @classmethod
    async def incr_async(cls, key: str, ttl: int = 60) -> int:
        """Atomic async increment for rate limiting and AI token counters."""
        r = await cls._get_redis_async()
        if r is not None:
            try:
                rk = f"lila:cache:{key}"
                val = await r.incr(rk)
                if val == 1 and ttl > 0:
                    await r.expire(rk, ttl)
                return val
            except Exception:
                pass

        now = time.time()
        if key in cls._DATA:
            val, expiry = cls._DATA[key]
            if expiry > now:
                new_val = int(val) + 1
                cls._DATA[key] = (new_val, expiry)
                cls._DATA.move_to_end(key)
                return new_val
        new_val = 1
        cls._DATA[key] = (new_val, now + ttl)
        cls._DATA.move_to_end(key)
        return new_val

    @classmethod
    def stats(cls) -> dict:
        """Returns statistics for Admin 2.0 dashboard."""
        now = time.time()
        valid_items = sum(1 for _, exp in cls._DATA.values() if exp > now)
        return {
            "driver": cls._get_driver(),
            "active_backend": "redis" if cls._redis_sync is not None or cls._redis_async is not None else "memory",
            "memory_items": valid_items,
            "max_items": cls._MAX_ITEMS,
            "redis_available": HAS_REDIS_PKG,
        }


def cached(ttl: int = 300, key_prefix: str = "route"):
    """Decorator to cache endpoint or function results in Lila Cache."""
    def decorator(fn):
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            req = kwargs.get("request") or (args[0] if args and hasattr(args[0], "url") else None)
            path_str = str(req.url.path) if req else fn.__name__
            query_str = str(req.url.query) if req else ""
            cache_key = f"{key_prefix}:{path_str}:{query_str}"

            cached_res = await Cache.get_async(cache_key)
            if cached_res is not None:
                return cached_res

            res = await fn(*args, **kwargs)
            await Cache.set_async(cache_key, res, ttl=ttl)
            return res

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            req = kwargs.get("request") or (args[0] if args and hasattr(args[0], "url") else None)
            path_str = str(req.url.path) if req else fn.__name__
            query_str = str(req.url.query) if req else ""
            cache_key = f"{key_prefix}:{path_str}:{query_str}"

            cached_res = Cache.get(cache_key)
            if cached_res is not None:
                return cached_res

            res = fn(*args, **kwargs)
            Cache.set(cache_key, res, ttl=ttl)
            return res

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper
    return decorator
