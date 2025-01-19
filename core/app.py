from starlette.applications import Starlette 
from starlette.exceptions import HTTPException
from core.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware
 

class App:
    def __init__(self, debug : bool =False,routes  = [],cors=None):
        self.routes =routes
        self.debug = debug
        self.cors=cors

    def start(self): 
        try:
            app=Starlette(debug=self.debug,routes=self.routes)
            app.add_exception_handler(404, self._404_page)
            if self.cors:
                app.add_middleware(
                CORSMiddleware,
                allow_origins=self.cors["origin"] or ["*"],  
                allow_credentials=self.cors["allow_credentials"] or True,
                allow_methods=self.cors["allow_methods"] or ["*"],  
                allow_headers=self.cors["allow_headers"] or["*"],  
            )

            return app
        except RuntimeError as e:
            print(f"{e}")

    def _404_page(self,request, exc):
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