from starlette.middleware import Middleware as StarletteMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from lila.core.responses import RedirectResponse, JSONResponse, HTMLResponse
from lila.core.request import Request
from lila.core.session import Session
from lila.core.logger import Logger
from app.config import DEBUG
from lila.core.auth import get_token
from lila.core.security import Security

import re
import traceback
import sys
from datetime import datetime, timedelta
import pydantic
from functools import wraps

# --- Utility Functions ---

async def check_session(request: Request, key: str = 'auth', return_JsonResponse: bool = True):
    """
    Checks if a session is active.
    """
    session_data = Session.unsign(key=key, request=request)
    if not session_data:
        if return_JsonResponse:
            return JSONResponse({"session": False, "success": False}, status_code=401)
        return None
    return session_data

async def check_token(request: Request):
    """
    Validates a JWT token from the Authorization header.
    """
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

# --- Class-based Middlewares ---

BLOCKED_PATHS = [
    "/RDWeb/Pages/", "/Remote/", "/wp-content/plugins/wp-statistics/readme.txt",
    "/goanywhere/lic/accept", "/etc/passwd", ".env", "wp-content", "docker/.env",
    "owa/auth/logon.aspx", "containers/json", "models", "autodiscover/autodiscover.json",
    "heapdump", "actuator/heapdump", "cgi-bin/vitogate.cgi", "CFIDE/wizards/common/utils.cfc",
    "var/www/html/.env", "home/user/.muttrc", "usr/local/spool/mail/root",
    "etc/postfix/master.cf", ".git", "scripts/.git/config", ".git/config",
    "modules/utils/.git/config", "/.git/config", "cgi-bin/luci/;stok=/locale",
    "//wp-includes/wlwmanifest.xml", "/wp-includes/wlwmanifest.xml", "/_profiler/phpinfo",
    "/etc/", "/vicidial/help_documentation.txt", "/sito/wp-includes/wlwmanifest.xml",
]

BLOCKED_REGEX = re.compile("|".join(map(re.escape, BLOCKED_PATHS)), re.IGNORECASE)
BLOCKED_IPS = {}
BLOCKED_RATELIMIT = {}

class SecurityShieldMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.now()

        if client_ip in BLOCKED_IPS:
            if now < BLOCKED_IPS[client_ip]:
                return HTMLResponse(content="Access Denied", status_code=403)
            else:
                del BLOCKED_IPS[client_ip]

        if len(BLOCKED_IPS) > 10000:
            expired_keys = [k for k, v in BLOCKED_IPS.items() if now > v]
            for k in expired_keys:
                del BLOCKED_IPS[k]

        url_path = request.url.path
        if BLOCKED_REGEX.search(url_path):
            BLOCKED_IPS[client_ip] = now + timedelta(minutes=10)
            Logger.warning(f"IP {client_ip} blocked for 10m. Malicious path: {url_path}")
            if DEBUG:
                print(f"IP {client_ip} blocked for 10m. Malicious path: {url_path}")
            return HTMLResponse(content="Access Denied", status_code=403)

        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = datetime.now()

        if client_ip not in BLOCKED_RATELIMIT:
            BLOCKED_RATELIMIT[client_ip] = []

        BLOCKED_RATELIMIT[client_ip] = [
            t for t in BLOCKED_RATELIMIT[client_ip] if now - t < timedelta(minutes=1)
        ]

        if len(BLOCKED_RATELIMIT) > 10000:
            empty_keys = [k for k, v in BLOCKED_RATELIMIT.items() if not v or (now - v[-1] > timedelta(minutes=1))]
            for k in empty_keys:
                del BLOCKED_RATELIMIT[k]

        if len(BLOCKED_RATELIMIT[client_ip]) >= 300:
            BLOCKED_IPS[client_ip] = now + timedelta(minutes=1)
            Logger.warning(f"IP {client_ip} rate limited for 1 minute. 300 requests in 1 minute.")
            if DEBUG:
                print(f"IP {client_ip} rate limited for 1 minute. 300 requests in 1 minute.")
            return JSONResponse(
                {"error": "Too many requests", "message": "Retry in 1 minute"}, 
                status_code=429
            )

        BLOCKED_RATELIMIT[client_ip].append(now)
        return await call_next(request)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """Sets security headers for the response."""
        response = await call_next(request)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Powered-By"] = "Lila Framework"
        return response

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            if isinstance(e, pydantic.ValidationError):
                errors = [{err["loc"][0]: err["msg"]} for err in e.errors()]
                msg_errors = " . ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                return JSONResponse(
                    {"success": False, "errors": errors, "msg": msg_errors},
                    status_code=400,
                )

            exc_type, exc_value, exc_tb = sys.exc_info()
            error_info = {
                "type": exc_type.__name__ if exc_type else "UnknownError",
                "message": str(e),
                "file": "unknown",
                "line": 0,
                "traceback": traceback.format_exc(),
            }

            if exc_tb:
                tb = exc_tb
                while tb.tb_next:
                    tb = tb.tb_next
                frame = tb.tb_frame
                error_info["file"] = frame.f_code.co_filename
                error_info["line"] = tb.tb_lineno
                error_info["function"] = frame.f_code.co_name

            Logger.error(f"Error: {error_info['type']} in {error_info['file']}:{error_info['line']}")
            Logger.error(f"Message: {error_info['message']}")
            Logger.error(f"Traceback:\n{error_info['traceback']}")

            is_fetch = request.headers.get("x-fetch") == "true" 
            msg = f"{error_info['type']} in {error_info['file']}:{error_info['line']}\nMessage: {error_info['message']}\nTraceback:\n{error_info['traceback']}"
            
            if is_fetch:
                if DEBUG:
                    return JSONResponse(
                        {
                            "error": msg, "success": False, "line": error_info["line"],
                            "function": error_info.get("function", "unknown"), "file": error_info["file"],
                            "type": error_info["type"], "message": str(e), "traceback": error_info["traceback"],
                        },
                        status_code=500,
                    )
                return JSONResponse({"error": "Internal Server Error", "success": False}, status_code=500)
            
            if DEBUG:
                return HTMLResponse(
                    content=f"<h1>Internal Server Error</h1><p>Something went wrong on our end.</p><pre>{msg}</pre>",
                    status_code=500,
                )
            return HTMLResponse(
                content="<h1>Internal Server Error</h1><p>Something went wrong on our end. Please try again later.</p>",
                status_code=500,
            )

class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_extensions=None, exclude_paths=None):
        super().__init__(app)
        self.exclude_extensions = exclude_extensions or {
            ".js", ".css", ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot",
        }
        self.exclude_paths = exclude_paths or {"public", "static", "assets", "favicon.ico"}

    async def should_log(self, path: str) -> bool:
        path_lower = path.lower()
        if any(path_lower.endswith(ext) for ext in self.exclude_extensions):
            return False
        if any(excluded in path_lower for excluded in self.exclude_paths):
            return False
        return True

    async def dispatch(self, request, call_next):
        if await self.should_log(request.url.path):
            Logger.info(await Logger.request(request=request))
        return await call_next(request)

# --- The Middleware Manager ---

def create_decorator(logic_func):
    """
    Helper to create a route decorator from a logic function.
    Supports both @decorator and @decorator(args).
    """
    @wraps(logic_func)
    def decorator(func=None, **kwargs):
        # Case: @decorator used without parens
        if func is not None and callable(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **f_kwargs):
                response = await logic_func(request)
                if response is not True and response is not None:
                    return response
                return await func(request, *args, **f_kwargs)
            return wrapper
        
        # Case: @decorator(...) used with parens
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
    """
    Lila Middleware Manager.
    Inherits from Starlette's Middleware for compatibility.
    """

    @staticmethod
    @create_decorator
    async def login_required(request: Request, key: str = "auth", url_return="/login"):
        session_data = await check_session(request=request, key=key, return_JsonResponse=False)
        if not session_data:
            if request.method != "GET":
                from lila.core.translate import Translate
                return JSONResponse({"success": False, "msg": Translate.t(key="Authentication required", request=request), "redirect": url_return}, status_code=401)
            return RedirectResponse(url=url_return)
        return True

    @staticmethod
    @create_decorator
    async def session_active(request: Request, key: str = "auth", url_return: str = "/dashboard"):
        session_data = await check_session(request=request, key=key, return_JsonResponse=False)
        if session_data:
            if request.method != "GET":
                from lila.core.translate import Translate
                return JSONResponse({"success": False, "msg": Translate.t(key="Session already active", request=request), "redirect": url_return}, status_code=400)
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
        """
        English: Route decorator that verifies the CSRF token on unsafe HTTP methods (POST, PUT, PATCH, DELETE).
        Safe methods (GET, HEAD, OPTIONS) are always allowed through.
        The token is read from the X-CSRF-Token header or from the 'csrf' field in the request body.

        Español: Decorador de ruta que verifica el token CSRF en metodos HTTP no seguros (POST, PUT, PATCH, DELETE).
        Los metodos seguros (GET, HEAD, OPTIONS) siempre son permitidos.
        El token se lee del header X-CSRF-Token o del campo 'csrf' del cuerpo del request.
        """
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


class FlashMiddleware(BaseHTTPMiddleware):
    """
    English: Middleware that processes and persists flash messages across requests.
    Español: Middleware que procesa y persiste mensajes flash a través de las peticiones.
    """
    async def dispatch(self, request: Request, call_next):
        import orjson
        from lila.core.session import serializer

        cookie_flashes = request.cookies.get("_flash")
        flashes = []
        if cookie_flashes:
            try:
                unsigned_data = serializer.loads(cookie_flashes, max_age=3600)
                flashes = orjson.loads(unsigned_data)
            except Exception:
                pass

        request.state._flash_messages = flashes
        request.state._new_flashes = []

        response = await call_next(request)

        if hasattr(request.state, "_new_flashes") and request.state._new_flashes:
            new_signed = serializer.dumps(orjson.dumps(request.state._new_flashes).decode())
            response.set_cookie(
                key="_flash",
                value=new_signed,
                max_age=3600,
                expires=3600,
                httponly=True,
                samesite="strict",
                path="/"
            )
        elif cookie_flashes:
            response.delete_cookie("_flash", path="/")

        return response

