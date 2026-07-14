import time
import pickle
from functools import wraps
from typing import Any, Optional
from lila.core.config import ENV_CONFIG
from app.config import DEBUG
from starlette.responses import Response

try:
    import redis
    import redis.asyncio as aioredis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

_REDIS_CLIENT = None
_REDIS_CLIENT_ASYNC = None

if _HAS_REDIS:
    _host = ENV_CONFIG.get("REDIS_HOST", "127.0.0.1")
    _port = ENV_CONFIG.get("REDIS_PORT", 6379)
    if _host:
        try:
            _client = redis.Redis(
                host=str(_host),
                port=int(_port or 6379),
                socket_connect_timeout=2,
                socket_timeout=2
            )
            _client.ping()
            _REDIS_CLIENT = _client
        except Exception:
            _REDIS_CLIENT = None
            
        try:
            _client_async = aioredis.Redis(
                host=str(_host),
                port=int(_port or 6379),
                socket_connect_timeout=2,
                socket_timeout=2
            )
            _REDIS_CLIENT_ASYNC = _client_async
        except Exception:
            _REDIS_CLIENT_ASYNC = None


class Cache:
    """Interface for caching values with Redis backend and in-memory fallback."""
    _DATA: dict[str, tuple[Any, float]] = {}
    MAX_ITEMS: int = 10000

    @classmethod
    def clean_expired(cls) -> None:
        """Clean expired keys from the in-memory backup cache."""
        now = time.time()
        keys_to_delete = [k for k, (_, expiry) in cls._DATA.items() if now > expiry]
        for k in keys_to_delete:
            del cls._DATA[k]

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300) -> None:
        """Set a key value pair in cache with time-to-live synchronously."""
        if _REDIS_CLIENT is not None:
            try:
                _REDIS_CLIENT.setex(name=key, time=ttl, value=pickle.dumps(value))
                if DEBUG:
                    print(f"REDIS CACHE: SET: {key} with {ttl} ttl, value: {value}")
                return
            except Exception:
                pass

        if len(cls._DATA) >= cls.MAX_ITEMS:
            cls.clean_expired()
            if len(cls._DATA) >= cls.MAX_ITEMS:
                cls.clear()
        cls._DATA[key] = (value, time.time() + ttl)

    @classmethod
    async def set_async(cls, key: str, value: Any, ttl: int = 300) -> None:
        """Set a key value pair in cache with time-to-live asynchronously."""
        if _REDIS_CLIENT_ASYNC is not None:
            try:
                await _REDIS_CLIENT_ASYNC.setex(name=key, time=ttl, value=pickle.dumps(value))
                if DEBUG:
                    print(f"REDIS CACHE (ASYNC): SET: {key} with {ttl} ttl, value: {value}")
                return
            except Exception:
                pass

        cls.set(key, value, ttl)

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Retrieve value for a key if it exists and is not expired synchronously."""
        if _REDIS_CLIENT is not None:
            try:
                serialized = _REDIS_CLIENT.get(key)
                if serialized is not None:
                    if DEBUG:
                        try:
                            remaining_ttl = _REDIS_CLIENT.ttl(key)
                            print(f"REDIS CACHE: GET: {key} with remaining ttl: {remaining_ttl}s")
                        except Exception:
                            print(f"REDIS CACHE: GET: {key}")
                    return pickle.loads(serialized)
                return None
            except Exception:
                pass

        item = cls._DATA.get(key)
        if item:
            val, expiry = item
            if time.time() < expiry:
                return val
            del cls._DATA[key]
        return None

    @classmethod
    async def get_async(cls, key: str) -> Optional[Any]:
        """Retrieve value for a key if it exists and is not expired asynchronously."""
        if _REDIS_CLIENT_ASYNC is not None:
            try:
                serialized = await _REDIS_CLIENT_ASYNC.get(key)
                if serialized is not None:
                    if DEBUG:
                        try:
                            remaining_ttl = await _REDIS_CLIENT_ASYNC.ttl(key)
                            print(f"REDIS CACHE (ASYNC): GET: {key} with remaining ttl: {remaining_ttl}s")
                        except Exception:
                            print(f"REDIS CACHE (ASYNC): GET: {key}")
                    return pickle.loads(serialized)
                return None
            except Exception:
                pass

        return cls.get(key)

    @classmethod
    def delete(cls, key: str) -> None:
        """Delete a key from cache synchronously."""
        if _REDIS_CLIENT is not None:
            try:
                _REDIS_CLIENT.delete(key)
                return
            except Exception:
                pass

        if key in cls._DATA:
            del cls._DATA[key]

    @classmethod
    async def delete_async(cls, key: str) -> None:
        """Delete a key from cache asynchronously."""
        if _REDIS_CLIENT_ASYNC is not None:
            try:
                await _REDIS_CLIENT_ASYNC.delete(key)
                return
            except Exception:
                pass

        cls.delete(key)

    @classmethod
    def clear(cls) -> None:
        """Clear all values from cache synchronously."""
        if _REDIS_CLIENT is not None:
            try:
                _REDIS_CLIENT.flushdb()
                return
            except Exception:
                pass

        cls._DATA.clear()

    @classmethod
    async def clear_async(cls) -> None:
        """Clear all values from cache asynchronously."""
        if _REDIS_CLIENT_ASYNC is not None:
            try:
                await _REDIS_CLIENT_ASYNC.flushdb()
                return
            except Exception:
                pass

        cls.clear()


def cached(ttl: int = 300):
    """Route decorator to cache GET requests asynchronously."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            if request.method != "GET":
                return await func(request, *args, **kwargs)

            query_params = tuple(sorted(request.query_params.items()))
            cache_key = f"route_cache:{request.url.path}:{query_params}"

            cached_data = await Cache.get_async(cache_key)
            if cached_data is not None:
                return Response(
                    content=cached_data["body"],
                    status_code=cached_data["status_code"],
                    media_type=cached_data["media_type"],
                    headers=cached_data["headers"]
                )

            response = await func(request, *args, **kwargs)
            if response.status_code == 200:
                body_bytes = getattr(response, "body", b"")
                cache_payload = {
                    "body": body_bytes,
                    "status_code": response.status_code,
                    "media_type": getattr(response, "media_type", "application/json"),
                    "headers": dict(response.headers)
                }
                await Cache.set_async(cache_key, cache_payload, ttl)

            return response
        return wrapper
    return decorator

