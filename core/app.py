from starlette.applications import Starlette
from core.responses import HTMLResponse,JSONResponse
from core.templates import render
from starlette.middleware.cors import CORSMiddleware
from core.logger import Logger
from pathlib import Path
from app.config import PATH_TEMPLATE_NOT_FOUND,DEBUG,PATH_TEMPLATES_HTML
from typing import List, Optional, Dict, Any
from starlette_compress import CompressMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from core.debug import DebugMiddleware, DebugModel, db
from core.routing import Router, CachedStaticFiles
from itertools import chain
from core.request import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

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
        public_folder: str = "public",
        public_url: str = "/",
        public_name: str = "public",
        on_startup: list = None,
        on_shutdown: list = None,
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
        if debug and DEBUG:
            middleware.append(Middleware(DebugMiddleware))
            routerDebug = Router("debug")

            @routerDebug.get("/")
            async def debug(request: Request):
                if DEBUG:
                    session = db.get_session()
                    try:
                        debugs = session.query(DebugModel).order_by(DebugModel.created_at.desc()).all()
                        debugs_list = [
                            {
                                "path": d.path,
                                "method": d.method,
                                "ip": d.ip,
                                "ram": d.ram,
                                "cpu": d.cpu,
                                "time_execution": d.time_execution,
                                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else ""
                            }
                            for d in debugs
                        ]
                    finally:
                        session.close()
                    is_fetch = request.query_params.get("fetch", False)
                    if is_fetch:
                        return JSONResponse(content=debugs_list)
                    response = render(request=request, template="lila/debug")
                    return response
                template = f"{PATH_TEMPLATES_HTML}{PATH_TEMPLATE_NOT_FOUND}"
                return render(request=request, template=template)

            @routerDebug.delete("/")
            async def delete_debug(request: Request):
                if DEBUG:
                    session = db.get_session()
                    try:
                        session.query(DebugModel).delete()
                        session.commit()
                    finally:
                        session.close()
                    return JSONResponse(content={"message": "Debug deleted successfully"})
                template = f"{PATH_TEMPLATES_HTML}{PATH_TEMPLATE_NOT_FOUND}"
                return render(request=request, template=template)

            debug_routes = routerDebug.get_routes()
            routes = list(chain(routes, debug_routes, [
                Mount(public_url, app=CachedStaticFiles(directory=public_folder), name=public_name)
            ]))
        else:
            routes=list(chain(routes,[
                Mount(public_url, app=CachedStaticFiles(directory=public_folder), name=public_name)
            ]))
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

        template_path = Path(f"{PATH_TEMPLATES_HTML}{PATH_TEMPLATE_NOT_FOUND}.html")
        if template_path.exists():
            return render(request=request, template=PATH_TEMPLATE_NOT_FOUND)
        return HTMLResponse(
            "<h1>404 Not Found</h1><p>The requested resource was not found on this server.</p>",
            status_code=404,
        )

    async def _500_page(self, request, exc):
        """
        Handle 500 Internal Server Error
        Shows detailed error page in DEBUG mode, generic error otherwise
        """
        import traceback
        import sys
        
        exc_type, exc_value, exc_tb = sys.exc_info()
        
        error_info = {
            'error_type': exc_type.__name__ if exc_type else 'InternalServerError',
            'error_message': str(exc),
            'traceback': traceback.format_exc(),
            'file': '',
            'line': 0,
            'function': '',
            'path': request.url.path,
            'method': request.method
        }
        
        if exc_tb:
            frame = exc_tb.tb_frame
            error_info['file'] = frame.f_code.co_filename
            error_info['line'] = exc_tb.tb_lineno
            error_info['function'] = frame.f_code.co_name
        
        # Always log to terminal
        print(f"\n{'='*80}")
        print(f"500 INTERNAL SERVER ERROR")
        print(f"{'='*80}")
        print(f"Path: {error_info['method']} {error_info['path']}")
        print(f"Error Type: {error_info['error_type']}")
        print(f"Error Message: {error_info['error_message']}")
        if error_info['file']:
            print(f"File: {error_info['file']}:{error_info['line']}")
            print(f"Function: {error_info['function']}")
        print(f"\nTraceback:\n{error_info['traceback']}")
        print(f"{'='*80}\n")
        
        Logger.error(
            f"500 Error: {error_info['method']} {error_info['path']} - "
            f"{error_info['error_type']}: {error_info['error_message']}"
        )
        
        if DEBUG:
            # Detailed HTML error page
            error_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>500 Internal Server Error</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        primary: '#1a73e8',
                        secondary: '#e91e63',
                        error: '#d32f2f',
                        surface: '#1e293b',
                        'bg-body': '#0f172a'
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-[#0f172a] text-slate-200 min-h-screen p-4 md:p-8 flex items-center justify-center font-sans transition-colors duration-300">
    <div class="w-full max-w-5xl bg-[#1e293b] border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
        <!-- Red warning Header -->
        <header class="bg-gradient-to-r from-red-600 to-red-800 p-6 md:p-8 border-b border-red-900 flex items-center gap-4">
            <span class="text-4xl animate-pulse">🚨</span>
            <div>
                <h1 class="text-2xl md:text-3xl font-black text-white tracking-tight">500 Internal Server Error</h1>
                <p class="text-sm text-red-200 font-semibold mt-1">An unexpected error occurred while processing your request.</p>
            </div>
        </header>

        <div class="p-6 md:p-8 space-y-6">
            <!-- Request Context -->
            <section class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="bg-slate-900/60 p-4 rounded-xl border border-slate-800/80">
                    <span class="text-[10px] font-black uppercase text-slate-500 tracking-wider block">HTTP Method</span>
                    <span class="text-md font-bold text-amber-400 mt-1 block">{error_info['method']}</span>
                </div>
                <div class="bg-slate-900/60 p-4 rounded-xl border border-slate-800/80">
                    <span class="text-[10px] font-black uppercase text-slate-500 tracking-wider block">Requested Path</span>
                    <span class="text-md font-bold text-slate-200 mt-1 block break-all">{error_info['path']}</span>
                </div>
                <div class="bg-slate-900/60 p-4 rounded-xl border border-slate-800/80">
                    <span class="text-[10px] font-black uppercase text-slate-500 tracking-wider block">Exception Class</span>
                    <span class="text-md font-bold text-red-400 mt-1 block break-all">{error_info['error_type']}</span>
                </div>
            </section>

            <!-- Error Message -->
            <section class="bg-red-950/20 border-l-4 border-red-500 p-5 rounded-r-xl">
                <h3 class="text-xs font-black uppercase text-red-400 tracking-wider mb-1">Error Message</h3>
                <p class="text-md font-semibold text-slate-200 leading-relaxed">{error_info['error_message']}</p>
            </section>
            
            {f'''<!-- Exception Location -->
            <section class="bg-slate-900/60 p-6 rounded-xl border border-slate-800/80 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <span class="text-[10px] font-black uppercase text-slate-500 tracking-wider block">File</span>
                    <span class="text-sm font-semibold text-amber-300 break-all mt-1 block">{error_info['file']}</span>
                </div>
                <div>
                    <span class="text-[10px] font-black uppercase text-slate-500 tracking-wider block">Line Number</span>
                    <span class="text-sm font-semibold text-slate-200 mt-1 block">{error_info['line']}</span>
                </div>
                <div>
                    <span class="text-[10px] font-black uppercase text-slate-500 tracking-wider block">Function</span>
                    <span class="text-sm font-semibold text-slate-200 mt-1 block">{error_info['function']}</span>
                </div>
            </section>''' if error_info['file'] else ''}

            <!-- Traceback Logs -->
            <section class="space-y-3">
                <h3 class="text-xs font-black uppercase text-slate-400 tracking-wider">Traceback Stack</h3>
                <div class="bg-black/80 border border-slate-800 rounded-2xl p-6 overflow-x-auto font-mono text-xs text-lime-400 leading-relaxed max-h-96">
                    <pre>{error_info['traceback']}</pre>
                </div>
            </section>
        </div>

        <footer class="bg-slate-900/40 p-4 border-t border-slate-800 text-center text-xs font-semibold text-slate-500">
            💡 This detailed diagnostic console is only visible when <code class="bg-slate-800 px-1.5 py-0.5 rounded text-slate-350">DEBUG=True</code> in your configuration.
        </footer>
    </div>
</body>
</html>
"""
            return HTMLResponse(error_html, status_code=500)
        else:
            # Production mode: generic error
            return HTMLResponse(
                "<h1>500 Internal Server Error</h1><p>An unexpected error occurred. Please try again later.</p>",
                status_code=500,
            )

def getenvironment(key: str, default: Any = None) -> Any:
    import os
    return os.getenv(key, default)
