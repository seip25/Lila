"""Lila Framework v2.0.x Session Manager.

Stateless signed-cookie sessions by default (perfect for 1-2 workers), with
transparent server-side storage (Redis if connected, in-memory otherwise) when
the payload is too large for a cookie or when Redis is the active driver.

Security guarantees:
- Never signs with an empty/placeholder key (see ``config.get_secret_key``).
- Never persists ``password``/hash fields inside the session payload.
- Cookies are ``Secure`` automatically when ``APP_URL`` is HTTPS.
"""

import secrets
from typing import Optional, Any, Union

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from lila.core.config import ENV_CONFIG, get_secret_key
from lila.core.responses import orjson_dumps, orjson_loads
from lila.core.cache import Cache


_SENSITIVE_KEYS = frozenset({"password", "password_hash", "hashed_password", "passwd"})
_MAX_COOKIE_PAYLOAD = 3000


def _get_session_serializer() -> URLSafeTimedSerializer:
    # get_secret_key() is fail-safe: it never returns "".
    return URLSafeTimedSerializer(get_secret_key(), salt="lila-session-salt")


def _default_secure() -> bool:
    return str(ENV_CONFIG.get("APP_URL", "") or "").strip().lower().startswith("https://")


def _clean_payload(value: Any) -> Any:
    """Drops sensitive keys recursively before signing a session cookie."""
    if isinstance(value, dict):
        return {
            k: _clean_payload(v)
            for k, v in value.items()
            if str(k).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_clean_payload(item) for item in value]
    return value


def _serialize_payload(value: Any) -> str:
    cleaned = _clean_payload(value)
    return orjson_dumps(cleaned).decode("utf-8")


class Session:
    """Manages user sessions via signed cookies or Cache/Redis backends."""

    # ──────────────────────────────────────────────────────────────────────────
    # Async API (v2)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    async def set_async(
        cls,
        value: Any = None,
        response: Any = None,
        cookie_name: str = "session",
        max_age: int = 86400,
        secure: Optional[bool] = None,
        http_only: bool = True,
        same_site: str = "lax",
        path: str = "/",
        request: Any = None,
        data: Any = None,
        key: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> bool:
        """Sets session value asynchronously. Returns False on failure (and logs it)."""
        if response is None:
            return False
        try:
            payload_val = data if data is not None else value
            target_cookie = key or cookie_name
            val_bytes = _serialize_payload(payload_val)
            serializer = _get_session_serializer()
            use_server_store = len(val_bytes) > _MAX_COOKIE_PAYLOAD

            if use_server_store:
                session_id = secrets.token_urlsafe(32)
                await Cache.set_async(f"session:{session_id}", val_bytes, ttl=max_age)
                cookie_payload = f"sid:{session_id}"
            else:
                cookie_payload = val_bytes

            signed = serializer.dumps(cookie_payload)
            response.set_cookie(
                key=target_cookie,
                value=signed,
                max_age=max_age,
                httponly=http_only,
                secure=_default_secure() if secure is None else secure,
                samesite=same_site,
                path=path,
                domain=domain,
            )
            return True
        except Exception as exc:  # pragma: no cover - defensive
            from lila.core.logger import Logger

            Logger.error(f"Session set error for cookie '{key or cookie_name}': {exc}", exception=exc)
            return False

    @classmethod
    async def set(
        cls,
        value_or_request: Any = None,
        response: Any = None,
        cookie_name: str = "session",
        max_age: int = 86400,
        secure: Optional[bool] = None,
        http_only: bool = True,
        same_site: str = "lax",
        path: str = "/",
        request: Any = None,
        data: Any = None,
        key: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> bool:
        """Async-compatible setter supporting both v2 and previous scaffold signatures."""
        # Allow Session.set(request, response, data=...) like the v2 docs.
        if data is not None:
            value = data
        elif hasattr(value_or_request, "cookies"):
            value = None
        else:
            value = value_or_request
        return await cls.set_async(
            value=value,
            response=response,
            cookie_name=key or cookie_name,
            max_age=max_age,
            secure=secure,
            http_only=http_only,
            same_site=same_site,
            path=path,
            domain=domain,
        )

    @classmethod
    def set_sync(
        cls,
        value: Any,
        response: Any,
        cookie_name: str = "session",
        max_age: int = 86400,
        secure: Optional[bool] = None,
        http_only: bool = True,
        same_site: str = "lax",
        path: str = "/",
        domain: Optional[str] = None,
    ) -> bool:
        """Sets session value synchronously."""
        if response is None:
            return False
        try:
            val_bytes = _serialize_payload(value)
            serializer = _get_session_serializer()
            use_server_store = len(val_bytes) > _MAX_COOKIE_PAYLOAD

            if use_server_store:
                session_id = secrets.token_urlsafe(32)
                Cache.set(f"session:{session_id}", val_bytes, ttl=max_age)
                cookie_payload = f"sid:{session_id}"
            else:
                cookie_payload = val_bytes

            signed = serializer.dumps(cookie_payload)
            response.set_cookie(
                key=cookie_name,
                value=signed,
                max_age=max_age,
                httponly=http_only,
                secure=_default_secure() if secure is None else secure,
                samesite=same_site,
                path=path,
                domain=domain,
            )
            return True
        except Exception as exc:  # pragma: no cover - defensive
            from lila.core.logger import Logger

            Logger.error(f"Session set_sync error for cookie '{cookie_name}': {exc}", exception=exc)
            return False

    @classmethod
    async def get_async(
        cls,
        request: Any,
        cookie_name: str = "session",
        max_age: int = 86400,
        key: Optional[str] = None,
    ) -> Optional[Any]:
        """Retrieves and deserializes a session value asynchronously."""
        target_cookie = key or cookie_name
        cookie_val = request.cookies.get(target_cookie)
        if not cookie_val and target_cookie == "session":
            cookie_val = request.cookies.get("auth")
        if not cookie_val:
            return None

        try:
            raw_payload = _get_session_serializer().loads(cookie_val, max_age=max_age)
        except (SignatureExpired, BadSignature, Exception):
            return None

        if isinstance(raw_payload, str) and raw_payload.startswith("sid:"):
            session_id = raw_payload[4:]
            data = await Cache.get_async(f"session:{session_id}")
            if data is None:
                return None
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8", errors="ignore")
            try:
                return orjson_loads(data)
            except Exception:
                return data

        try:
            return orjson_loads(raw_payload)
        except Exception:
            return raw_payload

    @classmethod
    async def get(
        cls,
        request: Any,
        cookie_name: str = "session",
        max_age: int = 86400,
        key: Optional[str] = None,
    ) -> Optional[Any]:
        return await cls.get_async(request, cookie_name=key or cookie_name, max_age=max_age)

    @classmethod
    def get_sync(
        cls,
        request: Any,
        cookie_name: str = "session",
        max_age: int = 86400,
    ) -> Optional[Any]:
        """Retrieves and deserializes a session value synchronously."""
        cookie_val = request.cookies.get(cookie_name)
        if not cookie_val and cookie_name == "session":
            cookie_val = request.cookies.get("auth")
        if not cookie_val:
            return None

        try:
            raw_payload = _get_session_serializer().loads(cookie_val, max_age=max_age)
        except (SignatureExpired, BadSignature, Exception):
            return None

        if isinstance(raw_payload, str) and raw_payload.startswith("sid:"):
            session_id = raw_payload[4:]
            data = Cache.get(f"session:{session_id}")
            if data is None:
                return None
            try:
                return orjson_loads(data)
            except Exception:
                return data

        try:
            return orjson_loads(raw_payload)
        except Exception:
            return raw_payload

    @classmethod
    async def delete_async(
        cls,
        request: Any = None,
        response: Any = None,
        cookie_name: str = "session",
        path: str = "/",
        key: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> bool:
        """Deletes session cookie and server-side storage asynchronously."""
        target_cookie = key or cookie_name
        # Handle swapped positional args (response, request).
        if request is not None and not hasattr(request, "cookies") and hasattr(request, "delete_cookie"):
            response, request = request, response

        if request is not None and hasattr(request, "cookies"):
            cookie_val = request.cookies.get(target_cookie)
            if cookie_val:
                try:
                    raw_payload = _get_session_serializer().loads(cookie_val)
                    if isinstance(raw_payload, str) and raw_payload.startswith("sid:"):
                        await Cache.delete_async(f"session:{raw_payload[4:]}")
                except Exception:
                    pass

        if response is not None and hasattr(response, "delete_cookie"):
            response.delete_cookie(key=target_cookie, path=path, domain=domain)
        return True

    @classmethod
    async def delete(
        cls,
        request_or_response: Any = None,
        response: Any = None,
        cookie_name: str = "session",
        path: str = "/",
        key: Optional[str] = None,
        request: Any = None,
        domain: Optional[str] = None,
    ) -> bool:
        """Deletes a session supporting both call styles."""
        req = request if request is not None else (
            request_or_response if hasattr(request_or_response, "cookies") else None
        )
        resp = response if response is not None else (
            request_or_response if hasattr(request_or_response, "delete_cookie") else None
        )
        return await cls.delete_async(
            request=req, response=resp, cookie_name=key or cookie_name, path=path, domain=domain
        )

    # ──────────────────────────────────────────────────────────────────────────
    # v1.3x compatibility helpers (synchronous, safe)
    # ──────────────────────────────────────────────────────────────────────────
    @classmethod
    def setSession(
        cls,
        new_val: Any = None,
        response: Any = None,
        name_cookie: str = "session",
        secure: Optional[bool] = None,
        samesite: str = "lax",
        max_age: int = 3600,
        domain: Optional[str] = None,
        http_only: bool = True,
        path: str = "/",
        **kwargs,
    ) -> bool:
        """Synchronous v1-compatible setter (``set_sync`` under the hood)."""
        return cls.set_sync(
            value=new_val,
            response=response,
            cookie_name=name_cookie,
            max_age=max_age,
            secure=secure,
            http_only=http_only,
            same_site=samesite,
            path=path,
            domain=domain,
        )

    @classmethod
    def getSessionValue(
        cls,
        request: Any,
        key: str = "auth",
        max_age: Optional[int] = 86400,
    ) -> Optional[Any]:
        """Synchronous v1-compatible unsign helper."""
        return cls.get_sync(request, cookie_name=key, max_age=max_age or 86400)

    @classmethod
    def getSession(cls, key: str, request: Any) -> Optional[str]:
        """Raw cookie accessor kept for v1 compatibility."""
        return request.cookies.get(key)

    @classmethod
    def deleteSession(cls, response: Any, name_cookie: str = "session") -> bool:
        """Synchronous v1-compatible cookie deletion."""
        try:
            response.delete_cookie(key=name_cookie)
            return True
        except Exception:
            return False

    # Backward-compatible aliases for the async v2 API.
    setSession_async = set_async
    getSession_async = get_async
    deleteSession_async = delete_async
