import time
from typing import Any, Optional

class Cache:
    """
    English: Simple in-memory cache with TTL support.
    Español: Caché simple en memoria con soporte para TTL.
    """
    _DATA: dict[str, tuple[Any, float]] = {}
    MAX_ITEMS: int = 10000

    @classmethod
    def clean_expired(cls) -> None:
        """
        English: Cleans up all expired items from the cache.
        Español: Limpia todos los elementos expirados de la caché.
        """
        now = time.time()
        keys_to_delete = [k for k, (_, expiry) in cls._DATA.items() if now > expiry]
        for k in keys_to_delete:
            del cls._DATA[k]

    @classmethod
    def set(cls, key: str, value: Any, ttl: int = 300) -> None:
        """
        English: Stores a value in the cache with a time-to-live.
        Español: Almacena un valor en la caché con un tiempo de vida.
        """
        if len(cls._DATA) >= cls.MAX_ITEMS:
            cls.clean_expired()
            if len(cls._DATA) >= cls.MAX_ITEMS:
                # If still full after cleaning, clear all to prevent memory exhaustion
                cls.clear()
                
        cls._DATA[key] = (value, time.time() + ttl)

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """
        English: Retrieves a value from the cache if it hasn't expired.
        Español: Recupera un valor de la caché si no ha expirado.
        """
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
        English: Removes a specific key from the cache.
        Español: Elimina una clave específica de la caché.
        """
        if key in cls._DATA:
            del cls._DATA[key]

    @classmethod
    def clear(cls) -> None:
        """
        English: Clears all items from the cache.
        Español: Limpia todos los elementos de la caché.
        """
        cls._DATA.clear()
