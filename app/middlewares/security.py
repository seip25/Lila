from starlette.middleware.base import BaseHTTPMiddleware
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from core.logger import Logger
from datetime import datetime, timedelta
from app.config import DEBUG
import traceback
import sys 


BLOCKED_PATHS =[
  "/RDWeb/Pages/",
  "/Remote/",
  "/wp-content/plugins/wp-statistics/readme.txt",
   "/goanywhere/lic/accept", 
   "/etc/passwd",
    ".env",
    "wp-content",
    "docker/.env",
    "owa/auth/logon.aspx",
    "containers/json",
    "models",
    "autodiscover/autodiscover.json",
    "heapdump",
    "actuator/heapdump",
    "cgi-bin/vitogate.cgi",
    "CFIDE/wizards/common/utils.cfc",
    "var/www/html/.env",
    "home/user/.muttrc",
    "usr/local/spool/mail/root",
    "etc/postfix/master.cf",
    ".git",
    "scripts/.git/config",
    ".git/config",
    "modules/utils/.git/config",
    "/.git/config",
   "cgi-bin/luci/;stok=/locale",
   "//wp-includes/wlwmanifest.xml",
   "/wp-includes/wlwmanifest.xml",
   "/_profiler/phpinfo",
   "/etc/",
   "/vicidial/help_documentation.txt",
  "/sito/wp-includes/wlwmanifest.xml",

]

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

        url_path = request.url.path.lower()
        is_malicious = any(p.lower() in url_path for p in BLOCKED_PATHS)

        if is_malicious:
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
        query_params = str(request.query_params).lower()
        xss_patterns = ["<script", "javascript:", "onerror=", "onload=", "alert("]
        
        if any(pattern in query_params for pattern in xss_patterns):
            return HTMLResponse(content="Potential XSS detected", status_code=400)

        response = await call_next(request)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Powered-By"]="Lila Framework"
        return response



class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            exc_type, exc_value, exc_tb = sys.exc_info()

            if exc_tb:
                tb = exc_tb
                while tb.tb_next:
                    tb = tb.tb_next

                frame = tb.tb_frame
                filename = frame.f_code.co_filename
                lineno = tb.tb_lineno

                error_info = {
                    "type": exc_type.__name__,
                    "message": str(e),
                    "file": filename,
                    "line": lineno,
                    "traceback": traceback.format_exc(),
                }

                Logger.error(
                    f"Error: {error_info['type']} in {error_info['file']}:{error_info['line']}"
                )
                Logger.error(f"Function: {error_info['function']}")
                Logger.error(f"Message: {error_info['message']}")
                Logger.error(f"Traceback:\n{error_info['traceback']}")
            is_fetch = request.headers.get("x-fetch") == "true" 
            msg = f""" 
                {error_info['type']} in {error_info['file']}:{error_info['line']}
                Function: {error_info['function']}
                Message: {error_info['message']}
                Traceback:
                {error_info['traceback']}
                """
            if is_fetch:
                if DEBUG:
                    response = JSONResponse(
                        {
                            "error": msg,
                            "success": False,
                            "line": lineno,
                            "function": function,
                            "file": filename,
                            "type": exc_type.__name__,
                            "message": str(e),
                            "traceback": traceback.format_exc(),
                        },
                        status_code=500,
                    )
                else:
                    response = JSONResponse(
                        {"error": "Internal Server Error", "success": False}, status_code=500
                    )
            else:
                response= HTMLResponse(
                    content=f"""<h1>Internal Server Error</h1><p>Something went wrong on our end. Please try again later.</p>
                    <pre>{msg}</pre>
                    """,
                    status_code=500,
                ) if DEBUG else HTMLResponse(
                    content="<h1>Internal Server Error</h1><p>Something went wrong on our end. Please try again later.</p>",
                    status_code=500,
            )
            return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Registra las peticiones entrantes omitiendo archivos estáticos y rutas configuradas.
    """
    def __init__(self, app, exclude_extensions=None, exclude_paths=None):
        super().__init__(app)
        self.exclude_extensions = exclude_extensions or {
            ".js", ".css", ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".ico",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
        }
        self.exclude_paths = exclude_paths or {
            "public",
            "static",
            "assets",
            "favicon.ico",
        }

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

        response = await call_next(request)
        return response
