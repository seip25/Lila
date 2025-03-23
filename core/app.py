from starlette.applications import Starlette
from core.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from core.logger import Logger
from core.middleware import ErrorHandlerMiddleware

class App:
    def __init__(self, debug: bool = False, routes=[], cors=None):
        self.routes = routes
        self.debug = debug
        self.cors = cors

    def start(self):
        try:
            app = Starlette(debug=self.debug, routes=self.routes)
            app.add_exception_handler(404, self._404_page)
            app.add_middleware(ErrorHandlerMiddleware)
            
            if self.cors:
                app.add_middleware(
                    CORSMiddleware,
                    allow_origins=self.cors.get("origin", ["*"]),
                    allow_credentials=self.cors.get("allow_credentials", True),
                    allow_methods=self.cors.get("allow_methods", ["*"]),
                    allow_headers=self.cors.get("allow_headers", ["*"]),
                )

            Logger.info("Application started successfully")
            return app
        except Exception as e:
            Logger.error(f"Error: {e}", exception=e)

    async def _404_page(self, request, exc):
        excluded_words={"public", "service-worker", "css","js","img","favicon.ico"}

        if all(word not in request.url.path for word in excluded_words ):
            Logger.warning(await Logger.request(request=request))
        
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>404 - Not Found</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 10%; }
                h1 { color: #ff6347; }
            </style>
        </head>
        <body>
            <h1>404 - Page Not Found</h1>
            <p>The page you are looking for does not exist.</p>
            <a href="/">Go back to home</a>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=404)
