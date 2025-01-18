from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from core.env import TITLE_PROJECT, VERSION_PROJECT, DESCRIPTION_PROJECT

class Router:
    def __init__(self) -> None:
        self.routes = []
    
    def route(self, path: str, methods: list[str] = ['GET']) -> None:
        try:
            def decorator(func):
                self.routes.append(Route(path=path, endpoint=func, methods=methods))
                return func
            return decorator
        except RuntimeError as e:
            print(f"Error : {e}")
    
    def mount(self, path: str = '/public', directory: str = 'static', name: str = 'static') -> None:
       
        try:
            self.routes.append(Mount(path, StaticFiles(directory=directory), name=name))
        except RuntimeError as e:
            print(f"Error :{e}")
    
    def get_routes(self) -> list:
        return self.routes

    def swagger_ui(self, path: str = '/docs', methods: list[str] = ['GET']) -> None:
        def swagger_docs(request: Request):
            html = '''
                <html>
                <head>
                    <title>API Documentation</title>
                    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.1.3/swagger-ui.css" />
                    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.1.3/swagger-ui-bundle.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4.1.3/swagger-ui-standalone-preset.js"></script>
                </head>
                <body>
                    <div id="swagger-ui"></div>
                    <script>
                        const ui = SwaggerUIBundle({
                            url: '/openapi.json',  // Este es el endpoint que genera el JSON de OpenAPI
                            dom_id: '#swagger-ui',
                            deepLinking: true,
                            presets: [
                                SwaggerUIBundle.presets.apis,
                                SwaggerUIStandalonePreset
                            ],
                            layout: "StandaloneLayout"
                        });
                    </script>
                </body>
            </html>

            '''
            return HTMLResponse(html)

        self.routes.append(Route(path=path, endpoint=swagger_docs, methods=methods))

    def openapi_json(self, path: str = '/openapi.json', methods: list[str] = ['GET']) -> None:
        def openapi_schema(request: Request):
            """Generar el esquema OpenAPI dinámicamente"""
            openapi_schema = {
                "openapi": "3.0.0",
                "info": {
                    "title": TITLE_PROJECT,
                    "version": VERSION_PROJECT,
                    "description": DESCRIPTION_PROJECT,
                },
                "paths": {}
            }
             
            for route in self.routes:
                if isinstance(route, Route):
                    methods = route.methods or ['GET']
                    path = route.path
                    if path not in ['/docs', '/openapi.json']:
                        for method in methods:
                            if path not in openapi_schema["paths"]:
                                openapi_schema["paths"][path] = {}
                            openapi_schema["paths"][path][method.lower()] = {
                                "summary": route.endpoint.__doc__ or "No description available",
                                "responses": {
                                    "200": {
                                        "description": "Successful Response"
                                    }
                                }
                            }
            return JSONResponse(openapi_schema)

        self.routes.append(Route(path=path, endpoint=openapi_schema, methods=methods))
