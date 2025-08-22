from starlette.applications import Starlette
from core.responses import HTMLResponse
from core.templates import render
from starlette.middleware.cors import CORSMiddleware
from core.logger import Logger 
import os 
from app.config import PATH_TEMPLATE_NOT_FOUND
from typing import List, Optional, Dict, Any


class App(Starlette):
    def __init__(
        self, 
        debug: bool = False, 
        routes: List = None, 
        cors: Optional[Dict[str, Any]] = None,
        middleware: List = None
    ):
        routes = routes or []
        
        middleware = middleware or []
        
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
        static_extensions = {'.js', '.css', '.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf', '.eot'}
        excluded_paths = {'public', 'static', 'assets', 'favicon.ico'}
        
        should_log = True
        path = request.url.path.lower()
        
        if any(path.endswith(ext) for ext in static_extensions) or any(excluded in path for excluded in excluded_paths):
            should_log = False
        
        if should_log:
            Logger.warning(f"404 Not Found: {request.url.path} - {await Logger.request(request=request)}")
        
        if os.path.exists(PATH_TEMPLATE_NOT_FOUND):
            response = render(request=request, template="404")
            return response
        else:
            html_content = "<h1>404 Not Found</h1><p>The requested resource was not found on this server.</p>"
            return HTMLResponse(content=html_content, status_code=404)