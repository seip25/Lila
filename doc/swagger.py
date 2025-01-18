from starlette.routing import Route
from core.routing import Router
from core.env import TITLE_PROJECT,VERSION_PROJECT,DESCRIPTION_PROJECT

class SwaggerDocs:
    def __init__(self, router: Router):
        self.router = router

    def generate_openapi(self) -> dict:
        openapi_schema = {
            "openapi": "3.0.0",
            "info": {
                "title": TITLE_PROJECT,
                "version": VERSION_PROJECT,
                "description": DESCRIPTION_PROJECT,
            },
            "paths": {}
        }
        for route in self.router.get_routes():
            if isinstance(route, Route):
                methods = route.methods or ["GET"]
                path = route.path
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
        return openapi_schema

