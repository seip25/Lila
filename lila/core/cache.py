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

if _HAS_REDIS:
    _host = ENV_CONFIG.get("REDIS_HOST","127.0.0.1")
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
            print("Redis not found")

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
        if _REDIS_CLIENT is not None:
            try:
                _REDIS_CLIENT.setex(name=key, time=ttl, value=pickle.dumps(value))
                if DEBUG:
                    print(f"REDIS CACHE: SET: {key} with {ttl} ttl,value: {value}")
                return
            except Exception:
                pass

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
    def delete(cls, key: str) -> None:
        """
        English: Deletes a key from cache.
        """
        if _REDIS_CLIENT is not None:
            try:
                _REDIS_CLIENT.delete(key)
                return
            except Exception:
                pass

        if key in cls._DATA:
            del cls._DATA[key]

    @classmethod
    def clear(cls) -> None:
        """
        English: Clears all values from cache.
        """
        if _REDIS_CLIENT is not None:
            try:
                _REDIS_CLIENT.flushdb()
                return
            except Exception:
                pass

        cls._DATA.clear()

