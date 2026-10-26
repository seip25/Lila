"""Lila Framework v2.0.0 Core Application.
Ultra-lightweight Starlette wrapper with:
- Pure ASGI optional middlewares (RateLimit, Logging, SecurityHeaders, CORS, GZip)
- Live-Reload SSE endpoint (/_lila/dev-reload)
- Dynamic OpenAPI 3.0 & Swagger documentation
- Automatic Router unpacking and static files mounting
"""

import os
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Union, Callable

from starlette.applications import Starlette
from starlette.routing import Route, Mount, BaseRoute
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response

from lila.core.config import ENV_CONFIG, get_base_path
from lila.core.routing import Router
from lila.core.responses import JSONResponse, HTMLResponse, StreamingResponse
from lila.core.templates import render
from lila.core.middleware import (
    PureASGISecurityHeadersMiddleware,
    PureASGIRateLimitMiddleware,
    PureASGILoggingMiddleware,
)
from lila.core.debug import PureASGIDebugMiddleware, DebugStore


BOOT_ID = uuid.uuid4().hex


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
    ):
        self._is_debug = debug if debug is not None else bool(ENV_CONFIG.get("DEBUG", True))
        self._routers: List[Router] = []
        self._raw_routes: List[BaseRoute] = []

        # 1. Unpack initial routes
        if routes:
            for item in routes:
                self._register_route_item(item)

        # 2. Mount Public static files
        static_path = public_dir or get_base_path("public")
        if not os.path.exists(static_path):
            pkg_public = os.path.join(os.path.dirname(__file__), "..", "public")
            if os.path.exists(pkg_public):
                static_path = os.path.abspath(pkg_public)

        if os.path.exists(static_path):
            self._raw_routes.append(
                Mount("/public", app=StaticFiles(directory=static_path), name="public")
            )
            # Also mount direct subpaths (/js, /img, /swagger, /favicon.ico)
            for sub in ("js", "img", "swagger"):
                sub_dir = os.path.join(static_path, sub)
                if os.path.exists(sub_dir):
                    self._raw_routes.append(
                        Mount(f"/{sub}", app=StaticFiles(directory=sub_dir), name=f"public_{sub}")
                    )

        # 3. Mount Dev-Reload SSE Endpoint
        if self._is_debug:
            self._raw_routes.append(
                Route("/_lila/dev-reload", endpoint=self._dev_reload_endpoint, methods=["GET"])
            )

        # 4. Mount OpenAPI & Swagger UI
        if openapi:
            self._raw_routes.append(
                Route("/openapi.json", endpoint=self._openapi_json_endpoint, methods=["GET"])
            )
            self._raw_routes.append(
                Route("/docs", endpoint=self._docs_ui_endpoint, methods=["GET"])
            )

        # 5. Build Middleware Stack
        middleware_stack: List[Middleware] = []

        if cors:
            cors_conf = cors if isinstance(cors, dict) else {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            }
            middleware_stack.append(Middleware(CORSMiddleware, **cors_conf))

        if gzip:
            gzip_conf = gzip if isinstance(gzip, dict) else {"minimum_size": 500}
            middleware_stack.append(Middleware(GZipMiddleware, **gzip_conf))

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

        # 6. Exception Handlers
        exception_handlers = {
            404: self._not_found_handler,
            500: self._server_error_handler,
        }

        # 7. Lifespan & Startup/Shutdown hooks (compatible with Starlette 0.30+ and 1.0+)
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

        super().__init__(
            debug=self._is_debug,
            routes=self._raw_routes,
            middleware=middleware_stack,
            exception_handlers=exception_handlers,
            lifespan=lifespan or _default_lifespan,
        )

    def _register_route_item(self, item: Any, prefix: str = "") -> None:
        if isinstance(item, Router):
            self._routers.append(item)
            for r in item.get_routes():
                self._raw_routes.append(r)
        elif isinstance(item, BaseRoute):
            self._raw_routes.append(item)
        elif isinstance(item, list):
            for sub in item:
                self._register_route_item(sub, prefix=prefix)

    def include_router(self, router: Union[Router, List[BaseRoute]], prefix: str = "") -> None:
        """Includes a Router instance or list of Routes at runtime with optional extra prefix."""
        if isinstance(router, Router):
            self._routers.append(router)
            for r in router.get_routes():
                self.routes.append(r)
        elif isinstance(router, list):
            for r in router:
                if isinstance(r, Router):
                    self.include_router(r, prefix=prefix)
                elif isinstance(r, BaseRoute):
                    self.routes.append(r)
        elif isinstance(router, BaseRoute):
            self.routes.append(router)

    async def _dev_reload_endpoint(self, request):
        """SSE endpoint notifying lila-client.js of server bootId changes."""
        async def event_generator():
            yield f'data: {{"type": "connected", "bootId": "{BOOT_ID}"}}\n\n'
            while True:
                await asyncio.sleep(15)
                yield f'data: {{"type": "ping"}}\n\n'

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    async def _openapi_json_endpoint(self, request):
        """Generates OpenAPI 3.0 schema dynamically."""
        paths: Dict[str, Any] = {}
        tags = set()

        for router in self._routers:
            for route_info in router.openapi_routes:
                p = route_info["path"]
                # Convert Starlette path parameters: /items/{id:int} -> /items/{id}
                openapi_path = ""
                for segment in p.split("/"):
                    if segment.startswith("{") and segment.endswith("}"):
                        param_name = segment[1:-1].split(":")[0]
                        openapi_path += f"/{{{param_name}}}"
                    else:
                        openapi_path += f"/{segment}" if segment else ""
                openapi_path = openapi_path or "/"

                if openapi_path not in paths:
                    paths[openapi_path] = {}

                for method in route_info["methods"]:
                    m_lower = method.lower()
                    paths[openapi_path][m_lower] = {
                        "summary": route_info["summary"],
                        "tags": route_info["tags"],
                        "responses": {
                            "200": {"description": "Successful Response"},
                            "422": {"description": "Validation Error"},
                        },
                    }
                    for t in route_info["tags"]:
                        tags.add(t)

        schema = {
            "openapi": "3.0.2",
            "info": {
                "title": ENV_CONFIG.get("TITLE_PROJECT", "Lila Application"),
                "version": ENV_CONFIG.get("VERSION_PROJECT", "2.0.0"),
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

    async def _not_found_handler(self, request, exc):
        if request.headers.get("accept", "").startswith("application/json") or request.url.path.startswith("/api/"):
            return JSONResponse({"success": False, "message": "Resource not found"}, status_code=404)
        return render(request, "lila/404", status_code=404)

    async def _server_error_handler(self, request, exc):
        if request.headers.get("accept", "").startswith("application/json") or request.url.path.startswith("/api/"):
            return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)
        return HTMLResponse("<h1>500 - Internal Server Error</h1>", status_code=500)

    async def _cleanup_resources(self):
        """Cleanly closes open database and cache handles on shutdown."""
        from lila.core.database import db
        await db.close_async()
