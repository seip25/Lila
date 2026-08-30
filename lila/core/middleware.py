from starlette.middleware import Middleware as StarletteMiddleware
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Scope, Receive, Send
from lila.core.responses import RedirectResponse, JSONResponse, HTMLResponse
from lila.core.request import Request
from lila.core.session import Session
from lila.core.logger import Logger
from app.config import DEBUG
from lila.core.auth import get_token
import orjson
import traceback
import sys
from datetime import datetime, timedelta
import pydantic
from functools import wraps


# --- Utility Functions ---

async def check_session(request: Request, key: str = "auth", return_JsonResponse: bool = True):
    """Checks if a user session is active."""
    session_data = Session.unsign(key=key, request=request)
    if not session_data:
        if return_JsonResponse:
            return JSONResponse({"session": False, "success": False}, status_code=401)
        return None
    return session_data


async def check_token(request: Request):
    """Validates a JWT Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            {"session": False, "message": "Missing Authorization header"}, status_code=401
        )

    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            {"session": False, "message": "Invalid token format. Use Bearer <token>"}, status_code=401
        )

    token_str = auth_header.split(" ")[1]
    token_data = get_token(token=token_str)
    if isinstance(token_data, JSONResponse):
        return token_data

    request.state.user = token_data
    return True


# --- Pure ASGI Middlewares (Zero AnyIO TaskGroup Overhead) ---

class SecurityHeadersMiddleware:
    """Pure ASGI middleware that attaches essential security headers to all HTTP responses."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Powered-By"] = "Lila Framework"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RateLimitMiddleware:
    """Pure ASGI rate limiting middleware backed by Redis with zero runtime overhead."""

    def __init__(self, app: ASGIApp, max_requests: int = 300, window_seconds: int = 60):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        from lila.core.cache import _get_redis_client_async
        redis_client = await _get_redis_client_async()
        if redis_client is not None:
            try:
                rate_limit_key = f"lila:rate_limit:{client_ip}"
                async with redis_client.pipeline() as pipe:
                    pipe.incr(rate_limit_key)
                    pipe.expire(rate_limit_key, self.window_seconds, nx=True)
                    res = await pipe.execute()
                request_count = res[0]

                if request_count > self.max_requests:
                    Logger.warning(f"IP {client_ip} exceeded rate limit: {request_count}/{self.max_requests}")
                    response = JSONResponse(
                        {"error": "Too many requests", "message": f"Retry in {self.window_seconds}s"},
                        status_code=429,
                    )
                    return await response(scope, receive, send)
            except Exception:
                pass

        await self.app(scope, receive, send)


class LoggingMiddleware:
    """Pure ASGI request logger skipping static asset paths for maximum performance."""

    def __init__(self, app: ASGIApp, exclude_extensions=None, exclude_paths=None):
        self.app = app
        self.exclude_extensions = exclude_extensions or {
            ".js", ".css", ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot",
        }
        self.exclude_paths = exclude_paths or {"/public", "/static", "/assets", "/favicon.ico"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        path_lower = path.lower()
        should_log = not any(path_lower.endswith(ext) for ext in self.exclude_extensions) and \
                     not any(path_lower.startswith(p) for p in self.exclude_paths)

        if should_log:
            method = scope.get("method", "GET")
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            Logger.info(f"{method} {path} - IP: {client_ip}")

        await self.app(scope, receive, send)


class FlashMiddleware:
    """Pure ASGI middleware for reading and writing signed session flash messages."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        cookie_flashes = request.cookies.get("_flash")
        flashes = []
        if cookie_flashes:
            try:
                from lila.core.session import serializer
                unsigned_data = serializer.loads(cookie_flashes, max_age=3600)
                flashes = orjson.loads(unsigned_data)
            except Exception:
                pass

        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["_flash_messages"] = flashes
        scope["state"]["_new_flashes"] = []

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state = scope.get("state", {})
                new_flashes = state.get("_new_flashes", [])
                headers = MutableHeaders(scope=message)
                if new_flashes:
                    from lila.core.session import serializer
                    new_signed = serializer.dumps(orjson.dumps(new_flashes).decode())
                    headers.append(
                        "set-cookie",
                        f"_flash={new_signed}; Max-Age=3600; Path=/; HttpOnly; SameSite=Strict",
                    )
                elif cookie_flashes:
                    headers.append(
                        "set-cookie",
                        "_flash=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict",
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)


# --- Route Decorator Factory ---

def create_decorator(logic_func):
    """Helper to create route decorators supporting both @decorator and @decorator(args)."""
    @wraps(logic_func)
    def decorator(func=None, **kwargs):
        if func is not None and callable(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **f_kwargs):
                response = await logic_func(request)
                if response is not True and response is not None:
                    return response
                return await func(request, *args, **f_kwargs)
            return wrapper

        def actual_decorator(f):
            @wraps(f)
            async def wrapper(request: Request, *args, **f_kwargs):
                response = await logic_func(request, **kwargs)
                if response is not True and response is not None:
                    return response
                return await f(request, *args, **f_kwargs)
            return wrapper
        return actual_decorator
    return decorator


class Middleware(StarletteMiddleware):
    """Lila Middleware Manager for route-level decorators and ASGI middleware wrapping."""

    @staticmethod
    @create_decorator
    async def login_required(request: Request, key: str = "auth", url_return: str = "/login"):
        session_data = await check_session(request=request, key=key, return_JsonResponse=False)
        if not session_data:
            if request.method != "GET":
                from lila.core.translate import Translate
                return JSONResponse(
                    {"success": False, "msg": Translate.t("Authentication required", request), "redirect": url_return},
                    status_code=401,
                )
            return RedirectResponse(url=url_return)
        return True

    @staticmethod
    @create_decorator
    async def session_active(request: Request, key: str = "auth", url_return: str = "/dashboard"):
        session_data = await check_session(request=request, key=key, return_JsonResponse=False)
        if session_data:
            if request.method != "GET":
                from lila.core.translate import Translate
                return JSONResponse(
                    {"success": False, "msg": Translate.t("Session already active", request), "redirect": url_return},
                    status_code=400,
                )
            return RedirectResponse(url=url_return)
        return True

    @staticmethod
    @create_decorator
    async def validate_token(request: Request):
        response = await check_token(request=request)
        if isinstance(response, JSONResponse):
            return response
        return True

    @staticmethod
    @create_decorator
    async def csrf(request: Request):
        """Verifies CSRF tokens on mutating HTTP methods (POST, PUT, PATCH, DELETE)."""
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        from lila.core.csrf import CSRF
        if not CSRF.verify(request):
            return JSONResponse({"success": False, "message": "Invalid or missing CSRF token"}, status_code=403)
        return True


# --- Aliases for convenience ---
login_required = Middleware.login_required
session_active = Middleware.session_active
validate_token = Middleware.validate_token
csrf = Middleware.csrf
