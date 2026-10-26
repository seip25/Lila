"""Lila Framework v2.0.0 Session Manager.
Supports signed cookie sessions with optional Redis backend storage.
"""

import secrets
from typing import Optional, Any, Union
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from lila.core.config import ENV_CONFIG
from lila.core.responses import orjson_dumps, orjson_loads
from lila.core.cache import Cache


def _get_session_serializer() -> URLSafeTimedSerializer:
    secret = str(ENV_CONFIG.get("SECRET_KEY", "lila-session-secret-key-change-me"))
    return URLSafeTimedSerializer(secret, salt="lila-session-salt")


class Session:
    """Manages user sessions via signed cookies or Cache/Redis backends.
    Supports both explicit sync/async methods and awaitable hybrid signatures.
    """

    @classmethod
    async def set_async(
        cls,
        value: Any = None,
        response: Any = None,
        cookie_name: str = "session",
        max_age: int = 86400,
        secure: bool = False,
        http_only: bool = True,
        same_site: str = "lax",
        path: str = "/",
        request: Any = None,
        data: Any = None,
        key: Optional[str] = None,
    ) -> bool:
        """Sets session value asynchronously."""
        try:
            payload_val = data if data is not None else value
            target_cookie = key or cookie_name
            val_bytes = orjson_dumps(payload_val).decode("utf-8")
            serializer = _get_session_serializer()

            if Cache._get_driver() == "redis":
                session_id = secrets.token_urlsafe(32)
                await Cache.set_async(f"session:{session_id}", val_bytes, ttl=max_age)
                cookie_payload = f"sid:{session_id}"
            else:
                cookie_payload = val_bytes

            signed = serializer.dumps(cookie_payload)
            if response is not None:
                response.set_cookie(
                    key=target_cookie,
                    value=signed,
                    max_age=max_age,
                    httponly=http_only,
                    secure=secure,
                    samesite=same_site,
                    path=path,
                )
            return True
        except Exception:
            return False

    @classmethod
    async def set(
        cls,
        value_or_request: Any = None,
        response: Any = None,
        cookie_name: str = "session",
        max_age: int = 86400,
        secure: bool = False,
        http_only: bool = True,
        same_site: str = "lax",
        path: str = "/",
        request: Any = None,
        data: Any = None,
        key: Optional[str] = None,
    ) -> bool:
        """Async-compatible session setter supporting both v2 and auth scaffold signatures."""
        val = data if data is not None else value_or_request
        return await cls.set_async(
            value=val,
            response=response,
            cookie_name=key or cookie_name,
            max_age=max_age,
            secure=secure,
            http_only=http_only,
            same_site=same_site,
            path=path,
        )

    @classmethod
    def set_sync(
        cls,
        value: Any,
        response: Any,
        cookie_name: str = "session",
        max_age: int = 86400,
        secure: bool = False,
        http_only: bool = True,
        same_site: str = "lax",
        path: str = "/",
    ) -> bool:
        """Sets session value synchronously."""
        try:
            val_bytes = orjson_dumps(value).decode("utf-8")
            serializer = _get_session_serializer()

            if Cache._get_driver() == "redis":
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
                secure=secure,
                samesite=same_site,
                path=path,
            )
            return True
        except Exception:
            return False

    @classmethod
    async def get_async(
        cls, request: Any, cookie_name: str = "session", max_age: int = 86400, key: Optional[str] = None
    ) -> Optional[Any]:
        """Retrieves and deserializes session value asynchronously."""
        target_cookie = key or cookie_name
        cookie_val = request.cookies.get(target_cookie)
        if not cookie_val and target_cookie == "session":
            # Also check 'auth' cookie if set via auth scaffold
            cookie_val = request.cookies.get("auth")
        if not cookie_val:
            return None

        serializer = _get_session_serializer()
        try:
            raw_payload = serializer.loads(cookie_val, max_age=max_age)
        except (SignatureExpired, BadSignature, Exception):
            return None

        if isinstance(raw_payload, str) and raw_payload.startswith("sid:"):
            session_id = raw_payload[4:]
            data = await Cache.get_async(f"session:{session_id}")
            if data is not None:
                try:
                    return orjson_loads(data)
                except Exception:
                    return data
            return None

        try:
            return orjson_loads(raw_payload)
        except Exception:
            return raw_payload

    @classmethod
    async def get(
        cls, request: Any, cookie_name: str = "session", max_age: int = 86400, key: Optional[str] = None
    ) -> Optional[Any]:
        """Retrieves session value asynchronously."""
        return await cls.get_async(request, cookie_name=key or cookie_name, max_age=max_age)

    @classmethod
    def get_sync(
        cls, request: Any, cookie_name: str = "session", max_age: int = 86400
    ) -> Optional[Any]:
        """Retrieves and deserializes session value synchronously."""
        cookie_val = request.cookies.get(cookie_name)
        if not cookie_val and cookie_name == "session":
            cookie_val = request.cookies.get("auth")
        if not cookie_val:
            return None

        serializer = _get_session_serializer()
        try:
            raw_payload = serializer.loads(cookie_val, max_age=max_age)
        except (SignatureExpired, BadSignature, Exception):
            return None

        if isinstance(raw_payload, str) and raw_payload.startswith("sid:"):
            session_id = raw_payload[4:]
            data = Cache.get(f"session:{session_id}")
            if data is not None:
                try:
                    return orjson_loads(data)
                except Exception:
                    return data
            return None

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
    ) -> bool:
        """Deletes session cookie and Redis storage asynchronously."""
        target_cookie = key or cookie_name
        # Handle swapped positional args (response, key="auth", request=request)
        if request is not None and not hasattr(request, "cookies") and hasattr(request, "delete_cookie"):
            response, request = request, response

        if request is not None and hasattr(request, "cookies"):
            cookie_val = request.cookies.get(target_cookie)
            if cookie_val:
                try:
                    serializer = _get_session_serializer()
                    raw_payload = serializer.loads(cookie_val)
                    if isinstance(raw_payload, str) and raw_payload.startswith("sid:"):
                        session_id = raw_payload[4:]
                        await Cache.delete_async(f"session:{session_id}")
                except Exception:
                    pass

        if response is not None and hasattr(response, "delete_cookie"):
            response.delete_cookie(key=target_cookie, path=path)
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
    ) -> bool:
        """Deletes session asynchronously supporting both v2 and auth scaffold signatures."""
        req = request if request is not None else (request_or_response if hasattr(request_or_response, "cookies") else None)
        resp = response if response is not None else (request_or_response if hasattr(request_or_response, "delete_cookie") else None)
        return await cls.delete_async(request=req, response=resp, cookie_name=key or cookie_name, path=path)

    # Backward compatibility aliases
    setSession = set
    setSession_async = set_async
    getSession = get
    getSession_async = get_async
    deleteSession = delete
    deleteSession_async = delete_async
