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
from core.debug import DebugMiddleware,DebugModel 
from core.debug import db_session_debug
from core.routing import Router
from itertools import chain
from core.request import Request

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
        if debug and DEBUG:
            middleware.append(Middleware(DebugMiddleware))
            routerDebug=Router("debug")
            @routerDebug.get("/")
            async def debug(request:Request):
                if DEBUG:
                    debugs = db_session_debug.query(DebugModel).order_by(DebugModel.created_at.desc()).all()
                    debugs_list = []
                    for debug in debugs:
                        debugs_list.append({
                            "path": debug.path,
                            "method": debug.method,
                            "ip": debug.ip,
                            "ram": debug.ram,
                            "cpu": debug.cpu,
                            "time_execution": debug.time_execution,
                            "created_at": debug.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        })
                    is_fetch =request.query_params.get("fetch",False)
                    if is_fetch:
                        return JSONResponse(data=debugs_list)
                    response=render(request=request,template="lila/debug")
                    return response
                else:
                    template = f"{PATH_TEMPLATES_HTML}{PATH_TEMPLATE_NOT_FOUND}"
                    return render(request=request,template=template)
            @routerDebug.delete("/")
            async def delete_debug(request:Request):
                if DEBUG:
                    db_session_debug.query(DebugModel).delete()
                    db_session_debug.commit()
                    return JSONResponse(data={"message": "Debug deleted successfully"})
                else:
                    template = f"{PATH_TEMPLATES_HTML}{PATH_TEMPLATE_NOT_FOUND}"
                    return render(request=request,template=template)
            debug_routes=routerDebug.get_routes()
            routes=list(chain(routes,debug_routes))

        super().__init__(debug=debug, routes=routes, middleware=middleware)

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
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #252526;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: #d32f2f;
            color: white;
            padding: 20px 30px;
            border-bottom: 3px solid #b71c1c;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .header p {{
            margin: 5px 0 0 0;
            opacity: 0.9;
            font-size: 14px;
        }}
        .content {{
            padding: 30px;
        }}
        .error-section {{
            margin-bottom: 25px;
            background: #2d2d30;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #d32f2f;
        }}
        .error-section h2 {{
            margin: 0 0 15px 0;
            font-size: 18px;
            color: #569cd6;
        }}
        .error-section p {{
            margin: 8px 0;
            font-size: 14px;
        }}
        .traceback {{
            background: #1e1e1e;
            padding: 20px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.5;
            border: 1px solid #3e3e42;
        }}
        .traceback pre {{
            margin: 0;
            color: #ce9178;
        }}
        .label {{
            display: inline-block;
            background: #3e3e42;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 10px;
            color: #d4d4d4;
        }}
        .value {{
            color: #dcdcaa;
        }}
        .footer {{
            background: #2d2d30;
            padding: 15px 30px;
            text-align: center;
            font-size: 12px;
            color: #858585;
            border-top: 1px solid #3e3e42;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 500 Internal Server Error</h1>
            <p>An unexpected error occurred while processing your request.</p>
        </div>
        <div class="content">
            <div class="error-section">
                <h2>📡 Request Information</h2>
                <p><span class="label">Method</span><span class="value">{error_info['method']}</span></p>
                <p><span class="label">Path</span><span class="value">{error_info['path']}</span></p>
                <p><span class="label">Error Type</span><span class="value">{error_info['error_type']}</span></p>
            </div>
            
            <div class="error-section">
                <h2>💬 Error Message</h2>
                <p>{error_info['error_message']}</p>
            </div>
            
            {f'''<div class="error-section">
                <h2>📍 Location</h2>
                <p><span class="label">File</span><span class="value">{error_info['file']}</span></p>
                <p><span class="label">Line</span><span class="value">{error_info['line']}</span></p>
                <p><span class="label">Function</span><span class="value">{error_info['function']}</span></p>
            </div>''' if error_info['file'] else ''}
            
            <div class="error-section">
                <h2>🔍 Full Traceback</h2>
                <div class="traceback">
                    <pre>{error_info['traceback']}</pre>
                </div>
            </div>
        </div>
        <div class="footer">
            <p>💡 This detailed error page is only shown when DEBUG=True in your configuration</p>
        </div>
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
