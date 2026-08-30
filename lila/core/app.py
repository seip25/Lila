from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware import Middleware
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from itertools import chain
from pathlib import Path
from typing import List, Optional, Dict, Any

from lila.core.responses import HTMLResponse, JSONResponse
from lila.core.logger import Logger
from lila.core.request import Request
from lila.core.routing import Router
from lila.core.middleware import SecurityHeadersMiddleware, FlashMiddleware
from app.config import PATH_TEMPLATE_NOT_FOUND, DEBUG, PATH_TEMPLATES_HTML


class App(Starlette):
    """
    Main Lila Application class inheriting from Starlette.
    Configures pure ASGI middlewares, routing, and exception handlers.
    """

    def __init__(
        self,
        debug: bool = False,
        routes: List = None,
        cors: Optional[Dict[str, Any]] = None,
        middleware: List = None,
        trusted_hosts: Optional[List[str]] = None,
        public_folder: str = "public",
        public_url: str = "/",
        public_name: str = "public",
        translate: bool = True,
        debug_html: bool = False,
        secret_key: Optional[str] = None,
        title: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        lang_default: Optional[str] = None,
        path_log_base_dir: Optional[str] = None,
        path_template_not_found: Optional[str] = None,
        path_templates_html: Optional[str] = None,
        path_templates_markdown: Optional[str] = None,
        path_locales: Optional[str] = None,
        path_uploads: Optional[str] = None,
    ):
        import app.config as config_module

        if secret_key is not None:
            config_module.SECRET_KEY = secret_key
        if title is not None:
            config_module.TITLE_PROJECT = title
        if version is not None:
            config_module.VERSION_PROJECT = version
        if description is not None:
            config_module.DESCRIPTION_PROJECT = description
        if lang_default is not None:
            config_module.LANG_DEFAULT = lang_default
        if path_log_base_dir is not None:
            config_module.PATH_LOG_BASE_DIR = path_log_base_dir
        if path_template_not_found is not None:
            config_module.PATH_TEMPLATE_NOT_FOUND = path_template_not_found
        if path_templates_html is not None:
            if not path_templates_html.endswith("/"):
                path_templates_html += "/"
            config_module.PATH_TEMPLATES_HTML = path_templates_html
        if path_templates_markdown is not None:
            if not path_templates_markdown.endswith("/"):
                path_templates_markdown += "/"
            config_module.PATH_TEMPLATES_MARKDOWN = path_templates_markdown
        if path_locales is not None:
            config_module.PATH_LOCALES = path_locales
        if path_uploads is not None:
            config_module.PATH_UPLOADS = path_uploads

        from lila.core.translate import Translate
        Translate.translate_enabled = translate
        self.debug_html = debug_html

        routes = list(routes) if routes else []
        middleware = list(middleware) if middleware else []

        # Standard pure ASGI Security Headers and Flash cookies
        middleware.append(Middleware(SecurityHeadersMiddleware))
        middleware.append(Middleware(FlashMiddleware))

        if trusted_hosts:
            middleware.append(
                Middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
            )

        # Fallback static files mount for standalone development (Nginx handles /public in production)
        if Path(public_folder).exists():
            routes.append(
                Mount(public_url, app=StaticFiles(directory=public_folder), name=public_name)
            )

        super().__init__(
            debug=debug, routes=routes, middleware=middleware,
        )

        try:
            self.add_exception_handler(404, self._404_page)
            self.add_exception_handler(500, self._500_page)

            if cors:
                self.add_middleware(
                    CORSMiddleware,
                    allow_origins=cors.get("origin", ["*"]),
                    allow_credentials=cors.get("allow_credentials", True),
                    allow_methods=cors.get("allow_methods", ["*"]),
                    allow_headers=cors.get("allow_headers", ["*"]),
                )

            Logger.info("Application initialized successfully")
        except Exception as e:
            Logger.error(f"Error initializing application: {e}")

    async def _404_page(self, request: Request, exc):
        """Standard 404 handler returning JSON for API or HTML for web requests."""
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header or request.url.path.startswith("/api/"):
            return JSONResponse(
                {"success": False, "message": "Resource not found", "status_code": 404},
                status_code=404,
            )

        template_path = Path(f"{PATH_TEMPLATES_HTML}{PATH_TEMPLATE_NOT_FOUND}.jinja")
        if template_path.exists():
            try:
                from lila.core.templates import render
                return render(request=request, template=PATH_TEMPLATE_NOT_FOUND)
            except Exception:
                pass

        return HTMLResponse(
            "<h1>404 Not Found</h1><p>The requested resource was not found on this server.</p>",
            status_code=404,
        )

    async def _500_page(self, request: Request, exc):
        """Standard 500 handler showing diagnostic details in DEBUG mode."""
        import traceback
        import sys

        exc_type, _, exc_tb = sys.exc_info()

        error_info = {
            "error_type": exc_type.__name__ if exc_type else "InternalServerError",
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
            "file": "",
            "line": 0,
            "function": "",
            "path": request.url.path,
            "method": request.method,
        }

        if exc_tb:
            frame = exc_tb.tb_frame
            error_info["file"] = frame.f_code.co_filename
            error_info["line"] = exc_tb.tb_lineno
            error_info["function"] = frame.f_code.co_name

        Logger.error(
            f"500 Error: {error_info['method']} {error_info['path']} - "
            f"{error_info['error_type']}: {error_info['error_message']}"
        )

        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header or request.url.path.startswith("/api/"):
            if DEBUG:
                return JSONResponse(
                    {
                        "success": False,
                        "error": error_info["error_type"],
                        "message": error_info["error_message"],
                        "file": error_info["file"],
                        "line": error_info["line"],
                        "traceback": error_info["traceback"],
                    },
                    status_code=500,
                )
            return JSONResponse(
                {"success": False, "message": "Internal Server Error"}, status_code=500
            )

        if DEBUG:
            error_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>500 Internal Server Error</title>
</head>
<body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;padding:2rem;">
    <div style="max-width:900px;margin:0 auto;background:#1e293b;border-radius:12px;padding:2rem;box-shadow:0 10px 25px rgba(0,0,0,0.5);">
        <h1 style="color:#ef4444;margin-top:0;">🚨 500 Internal Server Error</h1>
        <p><strong>Path:</strong> {error_info['method']} {error_info['path']}</p>
        <p><strong>Type:</strong> {error_info['error_type']}</p>
        <p><strong>Message:</strong> {error_info['error_message']}</p>
        <p><strong>Location:</strong> {error_info['file']}:{error_info['line']} ({error_info['function']})</p>
        <h3>Traceback:</h3>
        <pre style="background:#020617;color:#a3e635;padding:1rem;border-radius:8px;overflow-x:auto;">{error_info['traceback']}</pre>
    </div>
</body>
</html>
"""
            return HTMLResponse(error_html, status_code=500)

        return HTMLResponse(
            "<h1>500 Internal Server Error</h1><p>An unexpected error occurred. Please try again later.</p>",
            status_code=500,
        )


def getenvironment(key: str, default: Any = None) -> Any:
    """Helper to retrieve environment variable."""
    import os
    return os.getenv(key, default)
