from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from core.env import TITLE_PROJECT, VERSION_PROJECT, DESCRIPTION_PROJECT
from typing import Any

class Router:
    def __init__(self) -> None:
        self.routes = []
        self.docs=[]
    
    def route(self, path: str, methods: list[str] = ['GET'],model=None) -> None:
        try:
            def decorator(func):
                self.routes.append(Route(path=path, endpoint=func, methods=methods))
                if not model ==None:
                    self.docs.append({"path":path,"model":model})
                
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
                                "summary": f"{route.name} ",
                                "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": self.get_params(route),
                                    }
                                }
                            }
                        },
                                "responses": {
                                    "200": {
                                        "description": route.endpoint.__doc__ or f"{route.name} function"
                                    }
                                }
                            }
            return JSONResponse(openapi_schema)
        self.routes.append(Route(path=path, endpoint=openapi_schema, methods=methods))
    
    def get_params(self,route):
        model = None
        parameters={}
        for doc in self.docs:
            if doc["path"]==route.path:
                model=doc["model"]

        if model :
            fields=model.__fields__
            for field,field_info in fields.items():
                field_type=self.pydantic_type_to_openapi(field_info=field_info)
                parameters[field]={
                            "name": field,
                            "required": field_info.required,
                            "name":field,
                            "type": field_type
                }
                
        return parameters
    
    def pydantic_type_to_openapi(self, field_info: Any) -> str:
        if field_info.type_ is str:
            return "string"
        elif field_info.type_ is int:
            return "integer"
        elif field_info.type_ is bool:
            return "boolean"
        elif field_info.type_ is float:
            return "number"
        return "string" 