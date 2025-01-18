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
