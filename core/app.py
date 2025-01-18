from starlette.applications import Starlette 
from starlette.exceptions import HTTPException
from core.responses import HTMLResponse

class App:
    def __init__(self, debug : bool =False,routes  = []):
        self.routes =routes
        self.debug = debug

    def start(self): 
        try:
            app=Starlette(debug=self.debug,routes=self.routes)
            app.add_exception_handler(404, self._404_page)
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