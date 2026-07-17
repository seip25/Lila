import time
import pickle
from typing import Any, Optional
from lila.core.config import ENV_CONFIG
from app.config import DEBUG

try:
    import redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

_REDIS_CLIENT = None
_REDIS_INITIALIZED = False
_REDIS_LAST_TRY = 0.0

def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_INITIALIZED, _REDIS_LAST_TRY
    if not _HAS_REDIS:
        return None
    now = time.time()
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if _REDIS_INITIALIZED and (now - _REDIS_LAST_TRY < 5.0):
        return None

    _host = ENV_CONFIG.get("REDIS_HOST", "127.0.0.1")
    _port = ENV_CONFIG.get("REDIS_PORT", 6379)
    if _host:
        try:
            _REDIS_LAST_TRY = now
            _client = redis.Redis(
                host=str(_host),
                port=int(_port or 6379),
                socket_connect_timeout=1.5,
                socket_timeout=1.5
            )
            _client.ping()
            _REDIS_CLIENT = _client
            _REDIS_INITIALIZED = True
            if DEBUG:
                print(f"✅ Redis connected: {_host}:{_port}")
            return _REDIS_CLIENT
        except Exception:
            _REDIS_CLIENT = None
            if not _REDIS_INITIALIZED and DEBUG:
                print("Redis not available, using in-memory fallback cache")
            _REDIS_INITIALIZED = True
    return None

class Cache:
    """
    English: Interface for caching values with Redis backend and in-memory fallback.
    """
    _DATA: dict[str, tuple[Any, float]] = {}
    MAX_ITEMS: int = 10000

    @classmethod
    def clean_expired(cls) -> None:
        """
        English: Cleans expired keys from the in-memory backup cache.
        """
        now = time.time()
        keys_to_delete = [k for k, (_, expiry) in cls._DATA.items() if now > expiry]
        for k in keys_to_delete:
            del cls._DATA[k]

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300) -> None:
        """
        English: Sets a key value pair in cache with time-to-live.
        """
        global _REDIS_CLIENT
        client = _get_redis_client()
        if client is not None:
            try:
                client.setex(name=key, time=ttl, value=pickle.dumps(value))
                if DEBUG:
                    print(f"REDIS CACHE: SET: {key} with {ttl} ttl,value: {value}")
                return
            except Exception:
                _REDIS_CLIENT = None

        if len(cls._DATA) >= cls.MAX_ITEMS:
            cls.clean_expired()
            if len(cls._DATA) >= cls.MAX_ITEMS:
                cls.clear()
        cls._DATA[key] = (value, time.time() + ttl)

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """
        English: Retrieves value for a key if it exists and is not expired.
        """
        global _REDIS_CLIENT
        client = _get_redis_client()
        if client is not None:
            try:
                serialized = client.get(key)
                if serialized is not None:
                    if DEBUG:
                        try:
                            remaining_ttl = client.ttl(key)
                            print(f"REDIS CACHE: GET: {key} with remaining ttl: {remaining_ttl}s")
                        except Exception:
                            print(f"REDIS CACHE: GET: {key}")
                    return pickle.loads(serialized)
                return None
            except Exception:
                _REDIS_CLIENT = None

        item = cls._DATA.get(key)
        if item:
            val, expiry = item
            if time.time() < expiry:
                return val
            del cls._DATA[key]
        return None

    @classmethod
    def delete(cls, key: str) -> None:
        """
        English: Deletes a key from cache.
        """
        global _REDIS_CLIENT
        client = _get_redis_client()
        if client is not None:
            try:
                client.delete(key)
                return
            except Exception:
                _REDIS_CLIENT = None

        if key in cls._DATA:
            del cls._DATA[key]

    @classmethod
    def clear(cls) -> None:
        """
        English: Clears all values from cache.
        """
        global _REDIS_CLIENT
        client = _get_redis_client()
        if client is not None:
            try:
                client.flushdb()
                return
            except Exception:
                _REDIS_CLIENT = None

        cls._DATA.clear()

