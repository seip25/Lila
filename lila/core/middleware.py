"""Lila Framework v2.0.0 High-Performance Pure ASGI Middlewares & Decorators.
Zero BaseHTTPMiddleware streaming overhead.
"""

import time
import re
import asyncio
from functools import wraps
from typing import Optional, Callable, Any, Union
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send

from lila.core.config import ENV_CONFIG
from lila.core.cache import Cache
from lila.core.logger import Logger
from lila.core.request import Request
from lila.core.session import Session
from lila.core.csrf import CSRF
from lila.core.responses import JSONResponse, RedirectResponse, HTMLResponse


BLOCKED_PATTERNS = re.compile(
    r"(\.\./|\.env|\.git/|etc/passwd|wp-content|actuator/|heapdump|owa/auth)",
    re.IGNORECASE,
)


class PureASGISecurityHeadersMiddleware:
    """Pure ASGI middleware injecting security headers and blocking directory traversal."""

    def __init__(self, app: ASGIApp, block_traversal: bool = True):
        self.app = app
        self.block_traversal = block_traversal

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self.block_traversal and BLOCKED_PATTERNS.search(path):
            response = HTMLResponse("Forbidden", status_code=403)
            await response(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"x-xss-protection", b"1; mode=block"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
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
        if scope["type"] != "http" or self.max_requests <= 0:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(("/_lila", "/favicon")):
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
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(("/_lila", "/favicon")):
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
            query = scope.get("query_string", b"").decode("utf-8")

            # Extract user agent
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
# Decorators for Route Handlers (usable with or without parentheses)
# ──────────────────────────────────────────────────────────────────────────────
def login_required(fn_or_redirect: Union[Callable, str] = "/login", session_key: str = "session"):
    """Decorator ensuring request has active user session (@login_required or @login_required('/login'))."""
    redirect_to = "/login" if callable(fn_or_redirect) else str(fn_or_redirect)

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req: Optional[Request] = kwargs.get("request")
            if req is None:
                for a in args:
                    if isinstance(a, Request):
                        req = a
                        break

            if req is None:
                return RedirectResponse(redirect_to)

            user = await Session.get_async(req, cookie_name=session_key)
            if not user:
                if req.headers.get("accept", "").startswith("application/json") or req.url.path.startswith("/api/"):
                    return JSONResponse({"success": False, "message": "Authentication required"}, status_code=401)
                return RedirectResponse(redirect_to)

            req.state.user = user
            return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
        return wrapper

    if callable(fn_or_redirect):
        return decorator(fn_or_redirect)
    return decorator


def session_active(fn_or_redirect: Union[Callable, str] = "/dashboard", session_key: str = "session"):
    """Redirects authenticated users away from guest-only pages (like /login or /register)."""
    redirect_to = "/dashboard" if callable(fn_or_redirect) else str(fn_or_redirect)

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req: Optional[Request] = kwargs.get("request")
            if req is None:
                for a in args:
                    if isinstance(a, Request):
                        req = a
                        break

            if req is not None:
                user = await Session.get_async(req, cookie_name=session_key)
                if user:
                    return RedirectResponse(redirect_to)

            return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
        return wrapper

    if callable(fn_or_redirect):
        return decorator(fn_or_redirect)
    return decorator


def admin_required(fn_or_redirect: Union[Callable, str] = "/admin/login", redirect_to: Optional[str] = None):
    """Decorator ensuring active user is an administrator."""
    target_redirect = redirect_to or ("/admin/login" if callable(fn_or_redirect) else str(fn_or_redirect))

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req: Optional[Request] = kwargs.get("request")
            if req is None:
                for a in args:
                    if isinstance(a, Request):
                        req = a
                        break

            if req is None:
                return RedirectResponse(target_redirect)

            admin_user = await Session.get_async(req, cookie_name="admin_session")
            if not admin_user:
                if req.headers.get("accept", "").startswith("application/json") or req.url.path.startswith("/admin/api/"):
                    return JSONResponse({"success": False, "message": "Admin authentication required"}, status_code=401)
                return RedirectResponse(target_redirect)

            req.state.admin = admin_user
            return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
        return wrapper

    if callable(fn_or_redirect):
        return decorator(fn_or_redirect)
    return decorator


def rate_limit(max_requests: int = 60, window_seconds: int = 60):
    """Decorator to rate-limit a specific route handler."""
    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            req: Optional[Request] = kwargs.get("request")
            if req is None:
                for a in args:
                    if isinstance(a, Request):
                        req = a
                        break

            client_ip = getattr(req.client, "host", "unknown") if req else "unknown"
            key = f"rl:route:{fn.__name__}:{client_ip}"
            count = await Cache.incr_async(key, ttl=window_seconds)

            if count > max_requests:
                return JSONResponse(
                    {"success": False, "error": "rate_limit_exceeded", "message": "Rate limit exceeded."},
                    status_code=429,
                    headers={"Retry-After": str(window_seconds)},
                )

            return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
        return wrapper
    return decorator


def csrf_protect(fn: Optional[Callable] = None):
    """Decorator verifying CSRF token on mutating requests (@csrf or @csrf_protect)."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            req: Optional[Request] = kwargs.get("request")
            if req is None:
                for a in args:
                    if isinstance(a, Request):
                        req = a
                        break

            if req and req.method in ("POST", "PUT", "DELETE", "PATCH"):
                if not CSRF.verify(req):
                    return JSONResponse({"success": False, "message": "Invalid or missing CSRF token"}, status_code=403)

            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper

    if callable(fn):
        return decorator(fn)
    return decorator


# Alias for backward compatibility (@csrf)
csrf = csrf_protect
