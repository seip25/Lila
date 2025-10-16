from starlette.applications import Starlette
from core.responses import HTMLResponse
from core.templates import render
from starlette.middleware.cors import CORSMiddleware
from core.logger import Logger
from pathlib import Path
from app.config import PATH_TEMPLATE_NOT_FOUND
from typing import List, Optional, Dict, Any
from starlette_compress import CompressMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware


STATIC_EXTENSIONS = {
    ".js",
    ".css",
    ".jpg",
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
EXCLUDED_PATHS = {"public", "static", "assets", "favicon.ico"}


class App(Starlette):
    def __init__(
        self,
        debug: bool = False,
        routes: List = None,
        cors: Optional[Dict[str, Any]] = None,
        middleware: List = None,
        compress_type: str = "gzip",
        trusted_hosts: Optional[List[str]] = None,
    ):
        routes = routes or []

        middleware = middleware or []
        middleware = list(middleware)
        middleware_compress = (
            CompressMiddleware if compress_type == "zstd" else GZipMiddleware
        )
        
        middleware.append(Middleware(middleware_compress))

        if trusted_hosts:
            middleware.append(
                Middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
            )

        super().__init__(debug=debug, routes=routes, middleware=middleware)

        try:
            self.add_exception_handler(404, self._404_page)

            if cors:
                self.add_middleware(
                    CORSMiddleware,
                    allow_origins=cors.get("origin", ["*"]),
                    allow_credentials=cors.get("allow_credentials", True),
                    allow_methods=cors.get("allow_methods", ["*"]),
                    allow_headers=cors.get("allow_headers", ["*"]),
                )

            Logger.info("Application started successfully")
        except Exception as e:
            Logger.error(f"Error initializing application: {e}", exception=e)

    async def _404_page(self, request, exc):
        path = request.url.path.lower()
        if not (
            any(path.endswith(ext) for ext in STATIC_EXTENSIONS)
            or any(p in path for p in EXCLUDED_PATHS)
        ):
            Logger.warning(
                f"404 Not Found: {request.url.path} - {await Logger.request(request=request)}"
            )

        template_path = Path(PATH_TEMPLATE_NOT_FOUND)
        if template_path.exists():
            return render(request=request, template="404")
        return HTMLResponse(
            "<h1>404 Not Found</h1><p>The requested resource was not found on this server.</p>",
            status_code=404,
        )
