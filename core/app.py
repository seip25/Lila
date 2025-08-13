from starlette.applications import Starlette
from core.responses import HTMLResponse
from core.templates import render
from starlette.middleware.cors import CORSMiddleware
from core.logger import Logger
from core.middleware import ErrorHandlerMiddleware
import os 

class App(Starlette):
    def __init__(self, debug: bool = False, routes=[], cors=None):
        super().__init__(debug=debug, routes=routes)
        try:
        
            self.add_exception_handler(404, self._404_page)
            self.add_middleware(ErrorHandlerMiddleware)
            
            if cors:
                self.add_middleware(
                    CORSMiddleware,
                    allow_origins=self.cors.get("origin", ["*"]),
                    allow_credentials=self.cors.get("allow_credentials", True),
                    allow_methods=self.cors.get("allow_methods", ["*"]),
                    allow_headers=self.cors.get("allow_headers", ["*"]),
                )

            Logger.info("Application started successfully")
        except Exception as e:
            Logger.error(f"Error: {e}", exception=e)

    
    async def _404_page(self, request, exc):
        excluded_words={"public", "service-worker", "css","js","img","favicon.ico"}

        if all(word not in request.url.path for word in excluded_words ):
            Logger.warning(await Logger.request(request=request))
        
        verify_404 = os.path.exists(f"templates/html/404.html")
        if not verify_404:
            html_content = "<h1>404 Not Found</h1><p>The requested resource was not found on this server.</p>"
            return HTMLResponse(content=html_content, status_code=404) 
        response = render(request=request, template="404")
        return response
