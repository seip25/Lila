"""Lila Framework v2.0.x Cache.

Drivers:
- ``memory`` (default): in-process LRU + TTL, perfect for 1-2 workers.
- ``redis``: used only when the package is installed AND the server is reachable.
  If Redis is configured but offline, Lila logs once and falls back to memory.
- ``file``: last-resort persistent JSON cache (``app/cache/data``).

No pickle is used for Redis values: cache poisoning cannot become RCE.
"""

import os
import json
import time
import inspect
import hashlib
import threading
from collections import OrderedDict
from functools import wraps
from typing import Any, Optional, Union

from lila.core.config import ENV_CONFIG, get_data_path
from lila.core.logger import Logger
from lila.core.responses import orjson_dumps, orjson_loads

try:  # optional; the actual import happens in has_redis() to keep `import lila` light
    import importlib.util

    HAS_REDIS_PKG = importlib.util.find_spec("redis") is not None
except Exception:
    HAS_REDIS_PKG = False

_redis_module = None

# Kept for backwards compatibility; use has_redis() before touching Redis.
_REDIS_IMPORTED = False


def has_redis() -> bool:
    global _REDIS_IMPORTED, HAS_REDIS_PKG, _redis_module
    if _REDIS_IMPORTED:
        return HAS_REDIS_PKG
    _REDIS_IMPORTED = True
    try:
        import redis as redis_module  # noqa: F401

        _redis_module = redis_module
        HAS_REDIS_PKG = True
    except ImportError:
        HAS_REDIS_PKG = False
    return HAS_REDIS_PKG


class Cache:
    """Zero-infra in-memory LRU cache with optional Redis/file drivers."""

    _driver: str = "memory"
    _configured: bool = False
    _options: dict = {}
    _DATA: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
    _MAX_ITEMS: int = 10000
    _DEFAULT_TTL: int = 300

    _redis_sync = None
    _redis_async = None
    _redis_failed_until: float = 0.0
    _redis_warned: bool = False
    _file_dir: Optional[str] = None
    _lock = threading.RLock()

    # --------------------------------------------------------------------------
    # Configuration
    # --------------------------------------------------------------------------
    @classmethod
    def configure(cls, driver: Optional[str] = None, options: Optional[dict] = None) -> None:
        if driver is None:
            driver = str(ENV_CONFIG.get("CACHE_DRIVER", "memory")).lower().strip()
        else:
            driver = str(driver).lower().strip()
        if driver not in ("memory", "redis", "file"):
            driver = "memory"

        cls._options = options or {}
        cls._MAX_ITEMS = max(
            1, int(cls._options.get("max_items", ENV_CONFIG.get("CACHE_MAX_ITEMS", 10000)) or 10000)
        )
        cls._DEFAULT_TTL = max(0, int(cls._options.get("default_ttl", ENV_CONFIG.get("CACHE_DEFAULT_TTL", 300)) or 300))

        if driver == "redis" and not has_redis():
            print(
                "[Lila Cache] Package 'redis' is not installed "
                "(run: pip install lila-framework[redis]). Falling back to in-memory cache."
            )
            driver = "memory"

        if driver == "file":
            raw_dir = str(cls._options.get("dir") or ENV_CONFIG.get("CACHE_DIR", "app/cache/data"))
            cls._file_dir = raw_dir if os.path.isabs(raw_dir) else get_data_path(raw_dir)
            try:
                os.makedirs(cls._file_dir, exist_ok=True)
            except Exception:
                driver = "memory"
                cls._file_dir = None
        else:
            cls._file_dir = None

        cls._driver = driver
        cls._configured = True
        cls._redis_sync = None
        cls._redis_async = None
        cls._redis_failed_until = 0.0

    @classmethod
    def _get_driver(cls) -> str:
        if not cls._configured:
            cls.configure()
        return cls._driver

    # --------------------------------------------------------------------------
    # Redis helpers (lazy import, one warning, no event-loop stalls on retry)
    # --------------------------------------------------------------------------
    @classmethod
    def _redis_settings(cls) -> dict:
        host = cls._options.get("host") or ENV_CONFIG.get("REDIS_HOST", "127.0.0.1")
        try:
            port = int(cls._options.get("port") or ENV_CONFIG.get("REDIS_PORT", 6379))
        except (TypeError, ValueError):
            port = 6379
        password = cls._options.get("password") or ENV_CONFIG.get("REDIS_PASSWORD", None) or None
        url = cls._options.get("url") or ENV_CONFIG.get("REDIS_URL", None) or None
        db = int(cls._options.get("db", 0) or 0)
        timeout = float(cls._options.get("socket_timeout", 0.75))
        return {"host": host, "port": port, "password": password, "url": url, "db": db, "timeout": timeout}

    @classmethod
    def _mark_redis_down(cls, exc: Exception) -> None:
        cls._redis_failed_until = time.time() + 60.0
        if not cls._redis_warned:
            cls._redis_warned = True
            Logger.warning(f"[Lila Cache] Redis unavailable ({exc}); using in-memory cache.")
        cls._redis_sync = None
        cls._redis_async = None

    @classmethod
    def _get_redis_sync(cls):
        if cls._get_driver() != "redis" or not has_redis():
            return None
        if cls._redis_sync is not None:
            return cls._redis_sync
        if time.time() < cls._redis_failed_until:
            return None

        settings = cls._redis_settings()
        try:
            if settings["url"]:
                client = _redis_module.from_url(
                    settings["url"],
                    socket_timeout=settings["timeout"],
                    socket_connect_timeout=settings["timeout"],
                    decode_responses=False,
                    retry=None,
                )
            else:
                client = _redis_module.Redis(
                    host=settings["host"],
                    port=settings["port"],
                    password=settings["password"],
                    db=settings["db"],
                    socket_timeout=settings["timeout"],
                    socket_connect_timeout=settings["timeout"],
                    decode_responses=False,
                    retry=None,
                )
            client.ping()
            cls._redis_sync = client
            return client
        except Exception as exc:
            cls._mark_redis_down(exc)
            return None

    @classmethod
    async def _get_redis_async(cls):
        if cls._get_driver() != "redis" or not has_redis():
            return None
        if cls._redis_async is not None:
            return cls._redis_async
        if time.time() < cls._redis_failed_until:
            return None

        settings = cls._redis_settings()
        try:
            import redis.asyncio as aioredis

            if settings["url"]:
                client = aioredis.from_url(
                    settings["url"],
                    socket_timeout=settings["timeout"],
                    socket_connect_timeout=settings["timeout"],
                    decode_responses=False,
                    retry=None,
                )
            else:
                client = aioredis.Redis(
                    host=settings["host"],
                    port=settings["port"],
                    password=settings["password"],
                    db=settings["db"],
                    socket_timeout=settings["timeout"],
                    socket_connect_timeout=settings["timeout"],
                    decode_responses=False,
                    retry=None,
                )
            await client.ping()
            cls._redis_async = client
            return client
        except Exception as exc:
            cls._mark_redis_down(exc)
            return None

    @classmethod
    def redis_client(cls):
        """Public sync Redis client (or None). Used by the background worker."""
        return cls._get_redis_sync()

    @classmethod
    async def redis_client_async(cls):
        """Public async Redis client (or None)."""
        return await cls._get_redis_async()

    # --------------------------------------------------------------------------
    # Serialization / file helpers
    # --------------------------------------------------------------------------
    @staticmethod
    def _serialize(value: Any) -> bytes:
        return orjson_dumps(value)

    @staticmethod
    def _deserialize(raw: bytes) -> Any:
        return orjson_loads(raw)

    @classmethod
    def _file_path(cls, key: str) -> Optional[str]:
        if not cls._file_dir:
            return None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(cls._file_dir, f"{digest}.json")

    @classmethod
    def _file_get(cls, key: str) -> Any:
        path = cls._file_path(key)
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                record = json.load(fh)
            if float(record.get("exp", 0)) <= time.time():
                try:
                    os.remove(path)
                except Exception:
                    pass
                return None
            return cls._deserialize(record["data"].encode("utf-8"))
        except Exception:
            return None

    @classmethod
    def _file_set(cls, key: str, value: Any, ttl: int) -> bool:
        path = cls._file_path(key)
        if not path:
            return False
        expiry = time.time() + ttl if ttl > 0 else float("inf")
        try:
            payload = {"exp": expiry, "data": cls._serialize(value).decode("utf-8"), "key": key}
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, path)
            return True
        except Exception:
            return False

    @classmethod
    def _file_delete(cls, key: str) -> None:
        path = cls._file_path(key)
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass

    @classmethod
    def _memory_get(cls, key: str) -> Any:
        now = time.time()
        with cls._lock:
            if key in cls._DATA:
                val, expiry = cls._DATA[key]
                if expiry > now:
                    cls._DATA.move_to_end(key)
                    return val
                del cls._DATA[key]
        return None

    @classmethod
    def _memory_set(cls, key: str, value: Any, ttl: int) -> bool:
        now = time.time()
        expiry = now + ttl if ttl > 0 else float("inf")
        with cls._lock:
            if len(cls._DATA) >= cls._MAX_ITEMS:
                expired = [k for k, (_, exp) in cls._DATA.items() if exp <= now]
                for k in expired:
                    cls._DATA.pop(k, None)
                while len(cls._DATA) >= cls._MAX_ITEMS:
                    cls._DATA.popitem(last=False)
            cls._DATA[key] = (value, expiry)
            cls._DATA.move_to_end(key)
        return True

    # --------------------------------------------------------------------------
    # Sync operations
    # --------------------------------------------------------------------------
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        driver = cls._get_driver()
        if driver == "redis":
            r = cls._get_redis_sync()
            if r is not None:
                try:
                    raw = r.get(f"lila:cache:{key}")
                    if raw is not None:
                        return cls._deserialize(raw)
                except Exception as exc:
                    cls._mark_redis_down(exc)
            if cls._file_dir:
                value = cls._file_get(key)
                if value is not None:
                    return value
        if driver == "file":
            value = cls._file_get(key)
            return default if value is None else value
        value = cls._memory_get(key)
        return default if value is None else value

    @classmethod
    def set(cls, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        ttl = ttl if ttl is not None else cls._DEFAULT_TTL
        driver = cls._get_driver()
        if driver == "redis":
            r = cls._get_redis_sync()
            if r is not None:
                try:
                    serialized = cls._serialize(value)
                except Exception:
                    return cls._memory_set(key, value, ttl)
                try:
                    r.set(f"lila:cache:{key}", serialized, ex=ttl if ttl > 0 else None)
                    return True
                except Exception as exc:
                    cls._mark_redis_down(exc)
            if cls._file_dir and cls._file_set(key, value, ttl):
                return True
            return cls._memory_set(key, value, ttl)
        if driver == "file":
            if cls._file_set(key, value, ttl):
                return True
            return cls._memory_set(key, value, ttl)
        return cls._memory_set(key, value, ttl)

    @classmethod
    def delete(cls, key: str) -> None:
        driver = cls._get_driver()
        if driver == "redis":
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
                except Exception as exc:
                    cls._mark_redis_down(exc)
        if "*" in key:
            prefix = key.split("*", 1)[0]
            with cls._lock:
                for k in [k for k in cls._DATA if k.startswith(prefix)]:
                    cls._DATA.pop(k, None)
        else:
            with cls._lock:
                cls._DATA.pop(key, None)
        if cls._file_dir:
            if "*" in key:
                # Deleting by prefix would need an index; preserve sessions.
                cls._file_clear(include_sessions=key.startswith("session:"))
            else:
                cls._file_delete(key)

    @classmethod
    def clear(cls, include_sessions: bool = False) -> None:
        driver = cls._get_driver()
        if driver == "redis":
            r = cls._get_redis_sync()
            if r is not None:
                try:
                    cursor = 0
                    while True:
                        cursor, keys = r.scan(cursor=cursor, match="lila:cache:*", count=100)
                        if keys:
                            to_delete = [
                                k for k in keys
                                if include_sessions or not k.startswith(b"lila:cache:session:")
                            ]
                            if to_delete:
                                r.delete(*to_delete)
                        if cursor == 0:
                            break
                except Exception as exc:
                    cls._mark_redis_down(exc)
        with cls._lock:
            if include_sessions:
                cls._DATA.clear()
            else:
                for k in [k for k in cls._DATA if not k.startswith("session:")]:
                    cls._DATA.pop(k, None)
        cls._file_clear(include_sessions=include_sessions)

    @classmethod
    def _file_clear(cls, include_sessions: bool = True) -> None:
        if not cls._file_dir or not os.path.isdir(cls._file_dir):
            return
        for name in os.listdir(cls._file_dir):
            if not name.endswith((".json", ".tmp")):
                continue
            path = os.path.join(cls._file_dir, name)
            if not include_sessions and name.endswith(".json"):
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        record = json.load(fh)
                    if str(record.get("key", "")).startswith("session:"):
                        continue
                except Exception:
                    pass
            try:
                os.remove(path)
            except Exception:
                pass

    @classmethod
    def incr(cls, key: str, ttl: int = 60) -> int:
        driver = cls._get_driver()
        if driver == "redis":
            r = cls._get_redis_sync()
            if r is not None:
                try:
                    rk = f"lila:cache:{key}"
                    value = r.incr(rk)
                    if value == 1 and ttl > 0:
                        r.expire(rk, ttl)
                    return int(value)
                except Exception as exc:
                    cls._mark_redis_down(exc)
        if driver == "file":
            current = cls._file_get(key)
            new_value = (int(current) if current is not None else 0) + 1
            cls._file_set(key, new_value, ttl)
            return new_value
        with cls._lock:
            now = time.time()
            current = cls._DATA.get(key)
            if current is not None and current[1] > now:
                new_value = int(current[0]) + 1
                cls._DATA[key] = (new_value, current[1])
                cls._DATA.move_to_end(key)
                return new_value
            cls._DATA[key] = (1, now + ttl)
            cls._DATA.move_to_end(key)
            return 1

    # --------------------------------------------------------------------------
    # Async operations
    # --------------------------------------------------------------------------
    @classmethod
    async def get_async(cls, key: str, default: Any = None) -> Any:
        driver = cls._get_driver()
        if driver == "redis":
            r = await cls._get_redis_async()
            if r is not None:
                try:
                    raw = await r.get(f"lila:cache:{key}")
                    if raw is not None:
                        return cls._deserialize(raw)
                except Exception as exc:
                    cls._mark_redis_down(exc)
            if cls._file_dir:
                value = cls._file_get(key)
                if value is not None:
                    return value
        if driver == "file":
            value = cls._file_get(key)
            return default if value is None else value
        value = cls._memory_get(key)
        return default if value is None else value

    @classmethod
    async def set_async(cls, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        ttl = ttl if ttl is not None else cls._DEFAULT_TTL
        driver = cls._get_driver()
        if driver == "redis":
            r = await cls._get_redis_async()
            if r is not None:
                try:
                    serialized = cls._serialize(value)
                except Exception:
                    return cls._memory_set(key, value, ttl)
                try:
                    await r.set(f"lila:cache:{key}", serialized, ex=ttl if ttl > 0 else None)
                    return True
                except Exception as exc:
                    cls._mark_redis_down(exc)
            if cls._file_dir and cls._file_set(key, value, ttl):
                return True
            return cls._memory_set(key, value, ttl)
        if driver == "file":
            if cls._file_set(key, value, ttl):
                return True
            return cls._memory_set(key, value, ttl)
        return cls._memory_set(key, value, ttl)

    @classmethod
    async def delete_async(cls, key: str) -> None:
        driver = cls._get_driver()
        if driver == "redis":
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
                except Exception as exc:
                    cls._mark_redis_down(exc)
        with cls._lock:
            if "*" in key:
                prefix = key.split("*", 1)[0]
                for k in [k for k in cls._DATA if k.startswith(prefix)]:
                    cls._DATA.pop(k, None)
            else:
                cls._DATA.pop(key, None)
        if cls._file_dir:
            if "*" in key:
                cls._file_clear(include_sessions=key.startswith("session:"))
            else:
                cls._file_delete(key)

    @classmethod
    async def clear_async(cls, include_sessions: bool = False) -> None:
        driver = cls._get_driver()
        if driver == "redis":
            r = await cls._get_redis_async()
            if r is not None:
                try:
                    cursor = 0
                    while True:
                        cursor, keys = await r.scan(cursor=cursor, match="lila:cache:*", count=100)
                        if keys:
                            to_delete = [
                                k for k in keys
                                if include_sessions or not k.startswith(b"lila:cache:session:")
                            ]
                            if to_delete:
                                await r.delete(*to_delete)
                        if cursor == 0:
                            break
                except Exception as exc:
                    cls._mark_redis_down(exc)
        with cls._lock:
            if include_sessions:
                cls._DATA.clear()
            else:
                for k in [k for k in cls._DATA if not k.startswith("session:")]:
                    cls._DATA.pop(k, None)
        cls._file_clear(include_sessions=include_sessions)

    @classmethod
    async def incr_async(cls, key: str, ttl: int = 60) -> int:
        driver = cls._get_driver()
        if driver == "redis":
            r = await cls._get_redis_async()
            if r is not None:
                try:
                    rk = f"lila:cache:{key}"
                    value = await r.incr(rk)
                    if value == 1 and ttl > 0:
                        await r.expire(rk, ttl)
                    return int(value)
                except Exception as exc:
                    cls._mark_redis_down(exc)
        if driver == "file":
            return cls.incr(key, ttl)
        with cls._lock:
            now = time.time()
            current = cls._DATA.get(key)
            if current is not None and current[1] > now:
                new_value = int(current[0]) + 1
                cls._DATA[key] = (new_value, current[1])
                cls._DATA.move_to_end(key)
                return new_value
            cls._DATA[key] = (1, now + ttl)
            cls._DATA.move_to_end(key)
            return 1

    @classmethod
    async def close_async(cls) -> None:
        if cls._redis_async is not None:
            try:
                await cls._redis_async.aclose()
            except Exception:
                pass
            cls._redis_async = None
        if cls._redis_sync is not None:
            try:
                cls._redis_sync.close()
            except Exception:
                pass
            cls._redis_sync = None

    @classmethod
    def close(cls) -> None:
        if cls._redis_sync is not None:
            try:
                cls._redis_sync.close()
            except Exception:
                pass
            cls._redis_sync = None

    @classmethod
    def stats(cls) -> dict:
        now = time.time()
        with cls._lock:
            valid_items = sum(1 for _, exp in cls._DATA.values() if exp > now)
        return {
            "driver": cls._get_driver(),
            "active_backend": (
                "redis" if cls._redis_sync is not None or cls._redis_async is not None
                else "file" if cls._driver == "file"
                else "memory"
            ),
            "memory_items": valid_items,
            "max_items": cls._MAX_ITEMS,
            "redis_available": has_redis(),
        }


def cached(ttl: int = 300, key_prefix: str = "route"):
    """Decorator to cache endpoint/function results.

    Only JSON-friendly results are cached. ``Response``/streaming objects are
    returned as-is. Cache keys include the request identity to avoid leaks.
    """
    def decorator(fn):
        def _cache_key(args, kwargs) -> str:
            req = kwargs.get("request") or (args[0] if args and hasattr(args[0], "url") else None)
            path_str = str(req.url.path) if req else fn.__name__
            query_str = str(req.url.query) if req else ""
            identity = ""
            if req is not None:
                fingerprint_src = f"{req.headers.get('cookie', '')}|{req.headers.get('authorization', '')}"
                identity = hashlib.sha256(fingerprint_src.encode("utf-8", errors="ignore")).hexdigest()[:16]
            return f"{key_prefix}:{fn.__module__}.{fn.__qualname__}:{path_str}:{query_str}:{identity}"

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            key = _cache_key(args, kwargs)
            cached_res = await Cache.get_async(key)
            if cached_res is not None:
                return cached_res
            res = fn(*args, **kwargs)
            if asyncio.iscoroutine(res):
                res = await res
            if isinstance(res, (dict, list, str, int, float, bool)):
                await Cache.set_async(key, res, ttl=ttl)
            return res

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            key = _cache_key(args, kwargs)
            cached_res = Cache.get(key)
            if cached_res is not None:
                return cached_res
            res = fn(*args, **kwargs)
            if isinstance(res, (dict, list, str, int, float, bool)):
                Cache.set(key, res, ttl=ttl)
            return res

        import asyncio

        return async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper
    return decorator

