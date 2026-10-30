"""Lila Framework v2.0.x Pure ASGI Middlewares & Decorators.

Zero BaseHTTPMiddleware streaming overhead. Static assets are excluded from
rate limiting/logging, and static responses get long-lived cache headers.
"""

import time
import re
import inspect
import asyncio
from functools import wraps
from typing import Optional, Callable, Any, Union
from urllib.parse import parse_qsl, urlencode

from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.middleware.gzip import GZipMiddleware

from lila.core.config import ENV_CONFIG
from lila.core.cache import Cache
from lila.core.logger import Logger
from lila.core.request import Request
from lila.core.session import Session
from lila.core.csrf import CSRF
from lila.core.responses import JSONResponse, RedirectResponse, HTMLResponse


BLOCKED_PATTERNS = re.compile(
    r"(^|/)(?:\.env|\.git)(?:/|$)"
    r"|(^|/)\.\.(?:/|$)"
    r"|etc/passwd|wp-content/|actuator/|heapdump|owa/auth",
    re.IGNORECASE,
)

_STATIC_PREFIXES = ("/public/", "/js/", "/img/", "/swagger/", "/uploads/")
_IGNORED_LOG_PREFIXES = _STATIC_PREFIXES + ("/_lila/", "/favicon", "/health")
_SENSITIVE_QUERY_KEYS = frozenset(
    {"token", "access_token", "refresh_token", "key", "api_key", "password", "secret", "csrf", "_csrf", "code"}
)


def _is_static_path(path: str) -> bool:
    return path.startswith(_STATIC_PREFIXES)


def _redact_query(query: str) -> str:
    if not query:
        return ""
    try:
        pairs = parse_qsl(query, keep_blank_values=True)
    except Exception:
        return query
    redacted = [
        (key, "***" if key.lower() in _SENSITIVE_QUERY_KEYS else value)
        for key, value in pairs
    ]
    return urlencode(redacted)


class PureASGICSRFMiddleware:
    """Global CSRF guard for JSON/header clients.

    HTML form bodies are verified by the ``@csrf`` decorator or
    ``@router.post(..., csrf=True)`` after the body is parsed.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        if method not in ("POST", "PUT", "PATCH", "DELETE") or _is_static_path(path):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_type = headers.get(b"content-type", b"").decode("latin-1").lower()
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            # Body forms are handled by the route-level CSRF check.
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if not CSRF.verify(request):
            response = JSONResponse(
                {"success": False, "message": "Invalid or missing CSRF token"}, status_code=403
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class PureASGISecurityHeadersMiddleware:
    """Pure ASGI middleware injecting security headers and blocking real traversal probes."""

    def __init__(self, app: ASGIApp, block_traversal: bool = True):
        self.app = app
        self.block_traversal = block_traversal

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self.block_traversal and BLOCKED_PATTERNS.search(path):
            if path.startswith(("/api/", "/admin/api/")) or "application/json" in str(
                scope.get("headers", [])
            ):
                response = JSONResponse({"success": False, "message": "Forbidden"}, status_code=403)
            else:
                response = HTMLResponse("Forbidden", status_code=403)
            await response(scope, receive, send)
            return

        is_https = scope.get("scheme") == "https"

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}

                def add(name: bytes, value: bytes) -> None:
                    if name not in existing:
                        headers.append((name, value))

                add(b"x-content-type-options", b"nosniff")
                add(b"x-frame-options", b"DENY")
                add(b"referrer-policy", b"strict-origin-when-cross-origin")
                add(b"permissions-policy", b"geolocation=(), microphone=(), camera=()")
                add(b"cross-origin-opener-policy", b"same-origin")
                if is_https:
                    add(b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class PureASGIGZipMiddleware:
    """GZip wrapper that never compresses the dev SSE stream."""

    def __init__(self, app: ASGIApp, **kwargs):
        self.app = app
        self.gzip_app = GZipMiddleware(app, **kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/_lila/"):
            await self.app(scope, receive, send)
            return
        await self.gzip_app(scope, receive, send)


class PureASGIStaticCacheMiddleware:
    """Adds Cache-Control headers to static assets (and immutable for versioned URLs)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or not _is_static_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        query = scope.get("query_string", b"").decode("latin-1", errors="ignore")
        versioned = any(part.startswith("v=") for part in query.split("&"))
        max_age = int(ENV_CONFIG.get("STATIC_CACHE_MAX_AGE", 86400) or 86400)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"cache-control" for name, _ in headers):
                    if versioned:
                        headers.append((b"cache-control", b"public, max-age=31536000, immutable"))
                    else:
                        headers.append((b"cache-control", f"public, max-age={max_age}".encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class PureASGIRateLimitMiddleware:
    """Pure ASGI rate limiter using Cache atomic increment."""

    def __init__(self, app: ASGIApp, max_requests: int = 300, window_seconds: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        path = scope.get("path", "") if scope["type"] == "http" else ""
        if (
            scope["type"] != "http"
            or self.max_requests <= 0
            or _is_static_path(path)
            or path.startswith(("/_lila", "/favicon", "/health"))
        ):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        key = f"rl:global:{client_ip}"
        count = await Cache.incr_async(key, ttl=self.window_seconds)

        if count > self.max_requests:
            resp = JSONResponse(
                {"success": False, "error": "rate_limit_exceeded", "message": "Too many requests. Please slow down."},
                status_code=429,
                headers={"Retry-After": str(self.window_seconds)},
            )
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)


class PureASGILoggingMiddleware:
    """Pure ASGI request logger without consuming body streams."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        path = scope.get("path", "") if scope["type"] == "http" else ""
        if scope["type"] != "http" or path.startswith(_IGNORED_LOG_PREFIXES):
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        status_holder = [200]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder[0] = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            method = scope.get("method", "GET")
            query = _redact_query(scope.get("query_string", b"").decode("utf-8", errors="ignore"))

            user_agent = ""
            for name, val in scope.get("headers", []):
                if name.lower() == b"user-agent":
                    user_agent = val.decode("utf-8", errors="ignore")
                    break

            Logger.log_request(
                client_ip=client_ip,
                method=method,
                path=path,
                query=query,
                status_code=status_holder[0],
                duration_ms=elapsed_ms,
                user_agent=user_agent,
            )


# ──────────────────────────────────────────────────────────────────────────────
# Route decorators
# ──────────────────────────────────────────────────────────────────────────────
def _find_request(args, kwargs) -> Optional[Request]:
    req = kwargs.get("request")
    if isinstance(req, Request):
        return req
    for arg in args:
        if isinstance(arg, Request):
            return arg
    return None


def login_required(fn_or_redirect: Union[Callable, str] = "/login", session_key: str = "session"):
    """Decorator ensuring the request has an active user session."""
    redirect_to = "/login" if callable(fn_or_redirect) else str(fn_or_redirect)

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req = _find_request(args, kwargs)
            if req is None:
                return RedirectResponse(redirect_to, status_code=303)

            user = await Session.get_async(req, cookie_name=session_key)
            if not user:
                if req.headers.get("accept", "").lower().startswith("application/json") or req.url.path.startswith("/api/"):
                    return JSONResponse({"success": False, "message": "Authentication required"}, status_code=401)
                return RedirectResponse(redirect_to, status_code=303)

            req.state.user = user
            result = fn(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper

    if callable(fn_or_redirect):
        return decorator(fn_or_redirect)
    return decorator


def session_active(fn_or_redirect: Union[Callable, str] = "/dashboard", session_key: str = "session"):
    """Redirects authenticated users away from guest-only pages (login/register)."""
    redirect_to = "/dashboard" if callable(fn_or_redirect) else str(fn_or_redirect)

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req = _find_request(args, kwargs)
            if req is not None:
                user = await Session.get_async(req, cookie_name=session_key)
                if user:
                    return RedirectResponse(redirect_to, status_code=303)
            result = fn(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper

    if callable(fn_or_redirect):
        return decorator(fn_or_redirect)
    return decorator


def admin_required(fn_or_redirect: Union[Callable, str] = "/admin/login", redirect_to: Optional[str] = None):
    """Decorator ensuring the active user is an administrator."""
    target_redirect = redirect_to or ("/admin/login" if callable(fn_or_redirect) else str(fn_or_redirect))

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req = _find_request(args, kwargs)
            if req is None:
                return RedirectResponse(target_redirect, status_code=303)

            admin_user = await Session.get_async(req, cookie_name="admin_session")
            if not admin_user:
                if (
                    req.headers.get("accept", "").lower().startswith("application/json")
                    or req.url.path.startswith("/admin/api/")
                ):
                    return JSONResponse({"success": False, "message": "Admin authentication required"}, status_code=401)
                return RedirectResponse(target_redirect, status_code=303)

            req.state.admin = admin_user
            result = fn(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper

    if callable(fn_or_redirect):
        return decorator(fn_or_redirect)
    return decorator


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Decorator to rate-limit a specific route handler."""
    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req = _find_request(args, kwargs)
            client_ip = getattr(req.client, "host", "unknown") if req else "unknown"
            key = f"rl:route:{fn.__module__}.{fn.__qualname__}:{client_ip}"
            count = await Cache.incr_async(key, ttl=window_seconds)

            if count > max_requests:
                return JSONResponse(
                    {"success": False, "error": "rate_limit_exceeded", "message": "Rate limit exceeded."},
                    status_code=429,
                    headers={"Retry-After": str(window_seconds)},
                )

            result = fn(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper
    return decorator


def csrf_protect(fn: Optional[Callable] = None):
    """Decorator verifying a CSRF token on mutating requests (supports HTML forms)."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            req = _find_request(args, kwargs)
            if req and req.method in ("POST", "PUT", "DELETE", "PATCH"):
                if not await CSRF.verify_async(req):
                    if req.headers.get("accept", "").lower().startswith("application/json"):
                        return JSONResponse(
                            {"success": False, "message": "Invalid or missing CSRF token"}, status_code=403
                        )
                    return HTMLResponse("Invalid or missing CSRF token", status_code=403)
            result = func(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper

    if callable(fn):
        return decorator(fn)
    return decorator


def create_decorator(func: Callable):
    """Turns a validation function into a reusable route decorator.

    Usage::

        @create_decorator
        async def check_admin(request, role="admin"):
            if request.state.user.get("role") != role:
                return JSONResponse({"error": "Unauthorized"}, status_code=403)
            return True

        @router.get("/admin")
        @check_admin
        async def admin(request): ...

        @router.get("/super")
        @check_admin(role="superadmin")
        async def superadmin(request): ...
    """

    def _wrap(route_fn: Callable, config: dict) -> Callable:
        @wraps(route_fn)
        async def inner(*args, **kwargs):
            req = _find_request(args, kwargs)
            if req is None:
                return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)
            result = func(req, **config) if req is not None else None
            if inspect.isawaitable(result):
                result = await result
            if result is not None and result is not True:
                return result
            output = route_fn(*args, **kwargs)
            return await output if asyncio.iscoroutine(output) else output

        return inner

    @wraps(func)
    def factory(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return _wrap(args[0], {})
        return lambda route_fn: _wrap(route_fn, dict(kwargs))

    return factory


def validate_token(fn: Optional[Callable] = None, header: str = "Authorization", key: str = "user_id"):
    """JWT validation decorator for API routes.

    Usage::

        @router.get("/api/me")
        @validate_token
        async def me(request):
            return {"user_id": request.state.jwt_user_id}
    """
    def decorator(route_fn: Callable):
        @wraps(route_fn)
        async def wrapper(*args, **kwargs):
            from lila.core.auth import JWT

            req = _find_request(args, kwargs)
            if req is None:
                return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)

            auth_value = req.headers.get(header)
            if not auth_value:
                return JSONResponse({"success": False, "message": "Missing Authorization header"}, status_code=401)

            data = JWT.decode(auth_value)
            if not data:
                return JSONResponse({"success": False, "message": "Invalid or expired token"}, status_code=401)

            req.state.jwt = data
            req.state.jwt_user_id = data.get(key)
            result = route_fn(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper

    if callable(fn):
        return decorator(fn)
    return decorator


# Compatibility aliases used by older guides.
csrf = csrf_protect
check_session = login_required
check_token = validate_token

# Names used in older middleware documentation.
from starlette.middleware import Middleware  # noqa: E402

LoggingMiddleware = PureASGILoggingMiddleware
SecurityHeadersMiddleware = PureASGISecurityHeadersMiddleware
RateLimitMiddleware = PureASGIRateLimitMiddleware
StaticCacheMiddleware = PureASGIStaticCacheMiddleware
