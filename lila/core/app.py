"""Lila Framework v2.0.x Core Application.

Ultra-lightweight Starlette wrapper with:
- Pure ASGI optional middlewares (RateLimit, Logging, SecurityHeaders, CORS, GZip)
- Live-Reload SSE endpoint (``/_lila/dev-reload``)
- Dynamic OpenAPI 3.0 & Swagger documentation
- Automatic Router unpacking and static files mounting
- Root routes for ``/favicon.ico``, ``/sitemap.xml`` and ``/robots.txt``
"""

import os
import sys
import uuid
import hashlib
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Union, Callable

from starlette.applications import Starlette
from starlette.routing import Route, Mount, WebSocketRoute, BaseRoute
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from lila.core.config import ENV_CONFIG, ConfigLoader, get_base_path, get_data_path, is_debug
from lila.core.routing import Router
from lila.core.responses import JSONResponse, HTMLResponse, StreamingResponse, FileResponse, Response
from lila.core.middleware import (
    PureASGISecurityHeadersMiddleware,
    PureASGIRateLimitMiddleware,
    PureASGILoggingMiddleware,
    PureASGIStaticCacheMiddleware,
    PureASGICSRFMiddleware,
    PureASGIGZipMiddleware,
    PureASGIDesktopGuardMiddleware,
)
from lila.core.debug import PureASGIDebugMiddleware, DebugStore


BOOT_ID = uuid.uuid4().hex


def _package_public_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public"))


_DEV_WATCH_EXTENSIONS = frozenset({
    ".jinja", ".html", ".css", ".js", ".json", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2", ".ttf",
})
_DEV_WATCH_SKIP_DIRS = frozenset({"__pycache__", "uploads", "node_modules", ".git", "app/cache"})


def _dev_watch_signature() -> str:
    """Cheap mtime+size fingerprint of edit-able dev assets (templates/static/locales)."""
    roots = [
        get_base_path("resources", "html"),
        get_base_path("public"),
        get_base_path("app", "locales"),
    ]
    parts = []
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name for name in dirnames
                if name not in _DEV_WATCH_SKIP_DIRS
                and os.path.join(dirpath, name) not in (
                    os.path.join(get_base_path("public"), "uploads"),
                    os.path.join(get_base_path("app"), "cache"),
                )
            ]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in _DEV_WATCH_EXTENSIONS:
                    continue
                path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                parts.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")
    parts.sort()
    return hashlib.sha256("\n".join(parts).encode("utf-8", "ignore")).hexdigest()


def _openapi_path(path: str) -> str:
    """Convert Starlette ``{id:int}`` segments to OpenAPI ``{id}``."""
    openapi_path = ""
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            param_name = segment[1:-1].split(":")[0]
            openapi_path += f"/{{{param_name}}}"
        else:
            openapi_path += f"/{segment}" if segment else ""
    return openapi_path or "/"


class App(Starlette):
    def __init__(
        self,
        routes: Optional[List[Any]] = None,
        debug: Optional[bool] = None,
        rate_limit: Optional[Union[int, dict]] = None,
        logging: bool = False,
        security: bool = False,
        cors: Optional[Union[bool, dict]] = None,
        gzip: Optional[Union[bool, dict]] = None,
        csrf: bool = False,
        openapi: bool = True,
        public_dir: Optional[str] = None,
        on_startup: Optional[List[Any]] = None,
        on_shutdown: Optional[List[Any]] = None,
        lifespan: Optional[Callable] = None,
        debug_html: bool = False,
        middleware: Optional[List[Any]] = None,
    ):
        # Ensure .env is loaded even when users import App directly (not app.config).
        ConfigLoader.load()
        self._is_debug = debug if debug is not None else is_debug()
        self._routers: List[Router] = []
        self._raw_routes: List[BaseRoute] = []
        self._openapi_extra: List[dict] = []
        self._project_public = public_dir or get_base_path("public")
        self._package_public = _package_public_dir()
        self._csrf = bool(csrf)

        # 1. Unpack initial routes
        if routes:
            for item in routes:
                self._register_route_item(item)

        # 2. Static assets (project first, bundled package as fallback).
        static_path = self._project_public if os.path.isdir(self._project_public) else self._package_public
        if os.path.isdir(static_path):
            self._raw_routes.append(
                Mount("/public", app=StaticFiles(directory=static_path), name="public")
            )

            # Always use the bundled client so projects generated by older Lila
            # versions receive client fixes (and the dev-reload marker/SSE logic).
            client_js = os.path.join(_package_public_dir(), "js", "lila-client.js")
            if os.path.isfile(client_js):
                self._raw_routes.append(
                    Route("/js/lila-client.js", endpoint=self._client_js_endpoint, methods=["GET"])
                )

            for sub in ("js", "img", "swagger"):
                candidates = [
                    os.path.join(self._project_public, sub),
                    os.path.join(self._package_public, sub),
                ]
                for sub_dir in candidates:
                    if os.path.isdir(sub_dir):
                        self._raw_routes.append(
                            Mount(f"/{sub}", app=StaticFiles(directory=sub_dir), name=f"public_{sub}")
                        )
                        break

        # 3. Uploads (project public/uploads by default, writable app-data in
        # a frozen desktop build). Do not create a bare "public" directory in
        # arbitrary working directories; the upload helper creates the
        # destination on demand and StaticFiles picks it up.
        if getattr(sys, "frozen", False):
            uploads_dir = get_data_path("uploads")
        else:
            uploads_dir = os.path.join(self._project_public, "uploads")
        if getattr(sys, "frozen", False) or os.path.isdir(self._project_public):
            try:
                os.makedirs(uploads_dir, exist_ok=True)
            except Exception:
                pass
        self._raw_routes.append(
            Mount(
                "/uploads",
                app=StaticFiles(directory=uploads_dir, check_dir=False),
                name="uploads",
            )
        )

        # 4. Root SEO/favicon files.
        self._raw_routes.append(Route("/favicon.ico", endpoint=self._favicon_endpoint, methods=["GET"]))
        self._raw_routes.append(Route("/sitemap.xml", endpoint=self._sitemap_endpoint, methods=["GET"]))
        self._raw_routes.append(Route("/robots.txt", endpoint=self._robots_endpoint, methods=["GET"]))

        # 5. Dev-Reload SSE endpoint
        if self._is_debug:
            self._raw_routes.append(
                Route("/_lila/dev-reload", endpoint=self._dev_reload_endpoint, methods=["GET"])
            )
            if debug_html:
                self._raw_routes.append(Route("/debug", endpoint=self._debug_endpoint, methods=["GET", "DELETE"]))
                self._raw_routes.append(Route("/debug/", endpoint=self._debug_endpoint, methods=["GET", "DELETE"]))

        # 6. OpenAPI & Swagger UI
        if openapi:
            self._raw_routes.append(
                Route("/openapi.json", endpoint=self._openapi_json_endpoint, methods=["GET"])
            )
            self._raw_routes.append(
                Route("/docs", endpoint=self._docs_ui_endpoint, methods=["GET"])
            )

        # 7. Middleware stack
        middleware_stack: List[Middleware] = []

        # Desktop mode: gate every request/WebSocket behind the local token
        # before static files or any route can respond. The token is set before
        # ``main`` is imported by lila desktop / the PyInstaller bootstrap.
        if os.environ.get("LILA_DESKTOP_TOKEN"):
            middleware_stack.append(Middleware(PureASGIDesktopGuardMiddleware))

        middleware_stack.append(Middleware(PureASGIStaticCacheMiddleware))

        if self._csrf:
            middleware_stack.append(Middleware(PureASGICSRFMiddleware))

        if cors:
            cors_conf = cors if isinstance(cors, dict) else {
                "allow_origins": ["*"],
                "allow_credentials": False,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            }
            middleware_stack.append(Middleware(CORSMiddleware, **cors_conf))

        if gzip:
            gzip_conf = gzip if isinstance(gzip, dict) else {"minimum_size": 500}
            middleware_stack.append(Middleware(PureASGIGZipMiddleware, **gzip_conf))

        if security:
            middleware_stack.append(Middleware(PureASGISecurityHeadersMiddleware))

        if rate_limit:
            rl_limit = rate_limit if isinstance(rate_limit, int) else rate_limit.get("max_requests", 300)
            rl_win = 60 if isinstance(rate_limit, int) else rate_limit.get("window", 60)
            middleware_stack.append(
                Middleware(PureASGIRateLimitMiddleware, max_requests=rl_limit, window_seconds=rl_win)
            )

        if logging:
            middleware_stack.append(Middleware(PureASGILoggingMiddleware))

        if self._is_debug:
            middleware_stack.append(Middleware(PureASGIDebugMiddleware))

        for extra in (middleware or []):
            middleware_stack.append(extra)

        exception_handlers = {
            404: self._not_found_handler,
            405: self._method_not_allowed_handler,
            500: self._server_error_handler,
        }

        startup_list = list(on_startup or [])
        shutdown_list = list(on_shutdown or [])
        shutdown_list.append(self._cleanup_resources)

        @asynccontextmanager
        async def _default_lifespan(app_instance):
            for fn in startup_list:
                res = fn()
                if asyncio.iscoroutine(res):
                    await res
            try:
                yield
            finally:
                for fn in shutdown_list:
                    res = fn()
                    if asyncio.iscoroutine(res):
                        await res

        if lifespan is not None:
            user_lifespan = lifespan

            @asynccontextmanager
            async def _combined_lifespan(app_instance):
                async with user_lifespan(app_instance) as state:
                    try:
                        yield state
                    finally:
                        await self._cleanup_resources()

            final_lifespan = _combined_lifespan
        else:
            final_lifespan = _default_lifespan

        super().__init__(
            debug=self._is_debug,
            routes=self._raw_routes,
            middleware=middleware_stack,
            exception_handlers=exception_handlers,
            lifespan=final_lifespan,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Routing helpers
    # ──────────────────────────────────────────────────────────────────────────
    def _register_route_item(self, item: Any, prefix: str = "") -> None:
        if isinstance(item, Router):
            self._routers.append(item)
            for r in item.get_routes():
                self._raw_routes.append(r)
        elif isinstance(item, BaseRoute):
            self._raw_routes.append(item)
            if isinstance(item, Route):
                self._register_raw_openapi(item)
        elif isinstance(item, list):
            for sub in item:
                self._register_route_item(sub, prefix=prefix)

    @staticmethod
    def _clone_route_with_prefix(route: BaseRoute, prefix: str) -> BaseRoute:
        prefix = (prefix or "").rstrip("/")
        if not prefix:
            return route
        path = f"{prefix}{route.path}"
        if isinstance(route, Route):
            return Route(
                path,
                endpoint=route.endpoint,
                methods=list(route.methods or ["GET"]),
                name=route.name,
                include_in_schema=False,
            )
        if isinstance(route, WebSocketRoute):
            return WebSocketRoute(path, endpoint=route.endpoint, name=route.name)
        if isinstance(route, Mount):
            return Mount(path, app=route.app, name=route.name)
        return route

    def include_router(self, router: Union[Router, List[BaseRoute]], prefix: str = "") -> None:
        """Include a Router or a list of Routes, optionally behind an extra prefix."""
        prefix = (prefix or "").rstrip("/")
        if isinstance(router, Router):
            if prefix:
                for r in router.get_routes():
                    self.routes.append(self._clone_route_with_prefix(r, prefix))
                if getattr(router, "openapi", True):
                    for info in router.openapi_routes:
                        entry = dict(info)
                        entry["path"] = f"{prefix}{info['path']}"
                        self._openapi_extra.append(entry)
            else:
                self._routers.append(router)
                for r in router.get_routes():
                    self.routes.append(r)
        elif isinstance(router, list):
            for r in router:
                if isinstance(r, Router):
                    self.include_router(r, prefix=prefix)
                elif isinstance(r, BaseRoute):
                    cloned = self._clone_route_with_prefix(r, prefix)
                    self.routes.append(cloned)
                    self._register_raw_openapi(r, prefix)
        elif isinstance(router, BaseRoute):
            cloned = self._clone_route_with_prefix(router, prefix)
            self.routes.append(cloned)
            self._register_raw_openapi(router, prefix)

    def _register_raw_openapi(self, route: BaseRoute, prefix: str = "") -> None:
        """Adds minimal OpenAPI metadata for raw Starlette routes."""
        if not isinstance(route, Route):
            return
        methods = [m.upper() for m in (route.methods or ["GET"]) if m.upper() not in ("HEAD", "OPTIONS")]
        if not methods:
            return
        path = f"{(prefix or '').rstrip('/')}{route.path}"
        self._openapi_extra.append({
            "path": path,
            "methods": methods,
            "summary": (route.name or route.path).replace("_", " ").strip().title(),
            "tags": [],
            "inspector": None,
        })

    # ──────────────────────────────────────────────────────────────────────────
    # Root files
    # ──────────────────────────────────────────────────────────────────────────
    def _first_existing(self, *paths: str) -> Optional[str]:
        for path in paths:
            if path and os.path.isfile(path):
                return path
        return None

    async def _client_js_endpoint(self, request):
        target = os.path.join(_package_public_dir(), "js", "lila-client.js")
        if not os.path.isfile(target):
            return Response(status_code=404)
        return FileResponse(
            target,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache" if self._is_debug else "public, max-age=3600"},
        )

    async def _favicon_endpoint(self, request):
        target = self._first_existing(
            os.path.join(self._project_public, "favicon.ico"),
            os.path.join(self._package_public, "favicon.ico"),
        )
        if target:
            return FileResponse(target, media_type="image/x-icon", headers={"Cache-Control": "public, max-age=86400"})
        return Response(status_code=404)

    async def _sitemap_endpoint(self, request):
        target = self._first_existing(
            get_base_path("sitemap.xml"),
            os.path.join(self._project_public, "sitemap.xml"),
        )
        if target:
            return FileResponse(
                target, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"}
            )
        return Response(status_code=404)

    async def _robots_endpoint(self, request):
        target = self._first_existing(
            get_base_path("robots.txt"),
            os.path.join(self._project_public, "robots.txt"),
        )
        if target:
            return FileResponse(
                target, media_type="text/plain", headers={"Cache-Control": "public, max-age=3600"}
            )
        return Response(status_code=404)

    # ──────────────────────────────────────────────────────────────────────────
    # Dev reload / OpenAPI / error handlers
    # ──────────────────────────────────────────────────────────────────────────
    async def _dev_reload_endpoint(self, request):
        """SSE endpoint for server restarts plus Jinja/static edits.

        Uvicorn only watches Python files unless ``watchfiles`` is installed, so
        Lila also fingerprints project templates/static/locales and tells the
        browser to reload when one changes. Jinja's ``auto_reload`` then picks
        up the new template on the next request.
        """

        async def event_generator():
            watch_enabled = ENV_CONFIG.get_bool("LILA_DEV_RELOAD", True)
            last_sig = await asyncio.to_thread(_dev_watch_signature) if watch_enabled else ""
            yield f'data: {{"type": "connected", "bootId": "{BOOT_ID}"}}\n\n'
            ticks = 0
            try:
                while True:
                    await asyncio.sleep(1)
                    if await request.is_disconnected():
                        return
                    ticks += 1
                    if watch_enabled:
                        current = await asyncio.to_thread(_dev_watch_signature)
                        if current != last_sig:
                            last_sig = current
                            try:
                                from lila.core.templates import clear_asset_cache
                                from lila.core.translate import Translate

                                clear_asset_cache()
                                Translate.clear_cache()
                            except Exception:
                                pass
                            yield f'data: {{"type": "template", "version": "{current[:16]}"}}\n\n'
                            ticks = 0
                    if ticks >= 15:
                        ticks = 0
                        yield 'data: {"type": "ping"}\n\n'
            except (asyncio.CancelledError, GeneratorExit):
                return

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def _debug_endpoint(self, request):
        """Debug dashboard/API. Only mounted when debug=True and debug_html=True."""
        from lila.core.debug import DebugStore, get_system_metrics
        from lila.core.templates import render

        if request.method == "DELETE":
            from lila.core.csrf import CSRF

            if not CSRF.verify(request):
                return JSONResponse({"success": False, "message": "Invalid or missing CSRF token"}, status_code=403)
            DebugStore.clear()
            return JSONResponse({"success": True, "message": "Debug history cleared."})
        if request.query_params.get("fetch") in ("1", "true", "True"):
            return JSONResponse({"metrics": get_system_metrics(), "history": DebugStore.get_all()})
        return render(
            request,
            "lila/debug",
            context={"history": DebugStore.get_all(), "metrics": get_system_metrics()},
        )

    async def _openapi_json_endpoint(self, request):
        """Generates an OpenAPI 3.0 schema dynamically."""
        paths: Dict[str, Any] = {}
        tags = set()

        def add_entry(route_info: dict) -> None:
            p = route_info["path"]
            openapi_path = _openapi_path(p)
            paths.setdefault(openapi_path, {})
            for method in route_info.get("methods", []):
                m_lower = method.lower()
                paths[openapi_path][m_lower] = {
                    "summary": route_info.get("summary", ""),
                    "tags": route_info.get("tags", []),
                    "responses": {
                        "200": {"description": "Successful Response"},
                        "422": {"description": "Validation Error"},
                    },
                }
                for t in route_info.get("tags", []):
                    tags.add(t)

        for router in self._routers:
            if not getattr(router, "openapi", True):
                continue
            for route_info in router.openapi_routes:
                add_entry(route_info)
        for route_info in self._openapi_extra:
            add_entry(route_info)

        schema = {
            "openapi": "3.0.2",
            "info": {
                "title": ENV_CONFIG.get("TITLE_PROJECT", "Lila Application"),
                "version": ENV_CONFIG.get("VERSION_PROJECT", "2.0"),
                "description": ENV_CONFIG.get("DESCRIPTION_PROJECT", "API documentation powered by Lila Framework"),
            },
            "paths": paths,
            "tags": [{"name": t} for t in sorted(tags)],
        }
        return JSONResponse(schema)

    async def _docs_ui_endpoint(self, request):
        """Renders Swagger UI."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Lila API Documentation</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="/swagger/swagger-ui.css">
    <link rel="shortcut icon" href="/favicon.ico">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="/swagger/swagger-ui-bundle.js"></script>
    <script src="/swagger/swagger-ui-standalone-preset.js"></script>
    <script>
    window.onload = function() {
        SwaggerUIBundle({
            url: "/openapi.json",
            dom_id: '#swagger-ui',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true
        });
    }
    </script>
</body>
</html>"""
        return HTMLResponse(html)

    def _wants_json(self, request) -> bool:
        accept = request.headers.get("accept", "").lower()
        path = request.url.path
        return (
            accept.startswith("application/json")
            or accept.startswith("*/*")
            or path == "/api"
            or path.startswith("/api/")
            or path.startswith("/admin/api/")
        )

    async def _not_found_handler(self, request, exc):
        if self._wants_json(request):
            return JSONResponse({"success": False, "message": "Resource not found"}, status_code=404)
        from lila.core.templates import render

        # Prefer the project's resources/html/404.jinja; fall back to the bundled one.
        project_404 = get_base_path("resources", "html", "404.jinja")
        template_name = "404" if os.path.isfile(project_404) else "lila/404"
        return render(request, template_name, status_code=404)

    async def _server_error_handler(self, request, exc):
        from lila.core.logger import Logger

        Logger.error(f"Unhandled error on {request.url.path}: {exc}", exception=exc)
        if self._wants_json(request):
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)
        return HTMLResponse("<h1>500 - Internal Server Error</h1>", status_code=500)

    async def _method_not_allowed_handler(self, request, exc):
        allowed = getattr(exc, "headers", None) or {}
        if self._wants_json(request):
            return JSONResponse(
                {"success": False, "message": "Method not allowed"},
                status_code=405,
                headers=allowed,
            )
        return HTMLResponse("<h1>405 - Method Not Allowed</h1>", status_code=405, headers=allowed)

    async def _cleanup_resources(self):
        """Closes database and cache handles on shutdown."""
        try:
            from lila.core.database import db

            await db.close_async()
        except Exception:
            pass
        try:
            from app.connections import connection

            if connection is not db:
                await connection.close_async()
        except Exception:
            pass
        try:
            from lila.core.cache import Cache

            await Cache.close_async()
        except Exception:
            pass
