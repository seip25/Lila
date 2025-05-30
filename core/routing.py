from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from core.env import TITLE_PROJECT, VERSION_PROJECT, DESCRIPTION_PROJECT
from typing import Any, Type, Optional, List
from pydantic import BaseModel
from argon2 import PasswordHasher
from core.helpers import generate_token_value,get_user_by_token
from core.logger import Logger
import datetime
import re
from functools import wraps

ph = PasswordHasher()


class Router:
    def __init__(self) -> None:
        self.routes = []
        self.docs = []

    def route(self, path: str, methods: list[str] = ["GET"], model=None) -> None:
        try:

            def decorator(func):
                self.routes.append(Route(path=path, endpoint=func, methods=methods))
                if model is not None:
                    self.docs.append({"path": path, "model": model})

                return func

            return decorator
        except RuntimeError as e:
            Logger.error(f"Error : {str(e)}")
            print(f"Error : {e}")

    def mount(
        self, path: str = "/public", directory: str = "static", name: str = "static"
    ) -> None:

        try:
            self.routes.append(Mount(path, StaticFiles(directory=directory), name=name))
        except RuntimeError as e:
            Logger.error(f"Error : {str(e)}")
            print(f"Error :{e}")

    def get_routes(self) -> list:
        return self.routes

    def swagger_ui(self, path: str = "/docs", methods: list[str] = ["GET"]) -> None:
        def swagger_docs(request: Request):
            html = """
                <html>
                <head>
                    <title>API Documentation</title>
                    <link rel="stylesheet" type="text/css" href="/public/swagger/swagger-ui.css" />
                    <script src="/public/swagger/swagger-ui-bundle.js"></script>
                    <script src="/public/swagger/swagger-ui-standalone-preset.js"></script>
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
            """
            return HTMLResponse(html)

        self.routes.append(Route(path=path, endpoint=swagger_docs, methods=methods))

    def openapi_json(
        self, path: str = "/openapi.json", methods: list[str] = ["GET"]
    ) -> None:
        def openapi_schema(request: Request):
            openapi_schema = {
                "openapi": "3.0.0",
                "info": {
                    "title": TITLE_PROJECT,
                    "version": VERSION_PROJECT,
                    "description": DESCRIPTION_PROJECT,
                },
                "paths": {},
            }

            for route in self.routes:
                if isinstance(route, Route):
                    methods = route.methods or ["GET"]
                    path = route.path
                    if path not in ["/docs", "/openapi.json"]:
                        for method in methods:
                            if path not in openapi_schema["paths"]:
                                openapi_schema["paths"][path] = {}
                            if method.lower() != "head":
                                openapi_schema["paths"][path][method.lower()] = {
                                    "summary": f"{route.name} ",
                                    **(
                                        {
                                            "requestBody": {
                                                "content": {
                                                    "application/json": {
                                                        "schema": {
                                                            "type": "object",
                                                            "properties": self.get_params(
                                                                route
                                                            ),
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        if method.lower() not in ["get", "delete"]
                                        else {}
                                    ),
                                    "parameters": [
                                        {
                                            "name": param,
                                            "in": "path",
                                            "required": True,
                                            "schema": {"type": "integer"},
                                        }
                                        for param in self.get_path_params(path)
                                    ],
                                    "responses": {
                                        "200": {
                                            "description": route.endpoint.__doc__
                                            or f"{route.name} function"
                                        }
                                    },
                                }

            return JSONResponse(openapi_schema)

        self.routes.append(Route(path=path, endpoint=openapi_schema, methods=methods))

    def get_path_params(self, path: str):
        matches = re.findall(r"{(\w+)(?::\w+)?}", path)
        return matches

    def get_params(self, route):
        model = None
        parameters = {}
        for doc in self.docs:
            if doc["path"] == route.path:
                model = doc["model"]
                break

        if model:
            fields = model.__fields__
            for field, field_info in fields.items():
                field_type = self.pydantic_type_to_openapi(field_info=field_info)
                parameters[field] = {
                    "name": field,
                    "required": field_info.required,
                    "name": field,
                    "type": field_type,
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

    def rest_crud_generate(
        self,
        connection,
        model_sql,
        model_pydantic: Type[BaseModel],
        select: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        active: bool = False,
        delete_logic: bool = False,
        middlewares: dict = None,
        jsonresponse_prefix:str='',
        user_id_session:bool| str=False
    ) -> None:
        self.name = f"/api/{model_sql.__tablename__}"

        def middleware(func):
            @wraps(func)
            async def middleware_wr(*args, **kwargs):
                if callable(func):
                    result = func(*args, **kwargs)
                    if hasattr(result, "__await__"):
                        return await result
                    return result

            return middleware_wr
        
        async def execute_middleware(self,type:str):
            if middlewares is not None and type in middlewares:
                        for middleware_get in middlewares[type]:
                            middleware_func = middleware(middleware_get)
                            response =await middleware_func(self)
                            if isinstance(response,JSONResponse):
                                return response

        def get_user_id_session(self):
            id_token =get_user_by_token(self)
            if isinstance(id_token,JSONResponse):
                return id_token
            return id_token
        
        
        async def get(self):
            try:
                response =await execute_middleware(self,type='get')
                if isinstance(response,JSONResponse):
                    return response

                columns = " , ".join(select) if select else "*"
                filters = f"WHERE active = 1" if active else ""
                params={"user_id":0}
                if user_id_session: 
                    
                    user_id=get_user_id_session(self)
                    if isinstance(user_id,JSONResponse):
                        return user_id
                    params[user_id_session]=user_id
                    filters +=f" AND {user_id_session}= :{user_id_session}"
                else:
                    params=None

                query = f"SELECT {columns} FROM {model_sql.__tablename__} {filters}"
                items = connection.query(query=query,params=params,return_rows=True)
                return JSONResponse(items) if jsonresponse_prefix =='' else JSONResponse({jsonresponse_prefix:items})
            except Exception as e:
                Logger.error(f"Error rest crud , GET: {str(e)}")

        async def post(self):
            response =await execute_middleware(self,type='post')
            if isinstance(response,JSONResponse):
                return response
            try:
                body = await self.json()
                model = model_pydantic(**body)
            except Exception as e:
                print(str(e))
                Logger.warning(f"Error rest_crud_generate - POST: {str(e)}")
                return JSONResponse({"success": False, "msg": str(e)}, status_code=400)
            columns_ = (
                " , ".join(columns)
                if columns
                else " , ".join((row) for row in list(model_pydantic.__fields__.keys()))
            )
            values = (
                " , ".join(f":{row}" for row in columns)
                if columns
                else " , ".join(
                    f":{row}" for row in list(model_pydantic.__fields__.keys())
                )
            )
            params = {
                field: getattr(model, field)
                for field in model_pydantic.__fields__.keys()
            }
            if "token" in params:
                params["token"] = generate_token_value()
            if "hash" in params:
                params["hash"] = generate_token_value()

            if "password" in params:
                params["password"] = ph.hash(params["password"])

            if "created_at" in body:
                params["created_at"] = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                columns_ += ",created_at"
                values += ",:created_at"

            if "created_date" in body:
                params["created_date"] = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                columns_ += ",created_date"
                values += ",:created_date"

            if user_id_session: 
                user_id=get_user_id_session(self)
                if isinstance(user_id,JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    columns_ += f", {user_id_session}"
                    values += f", :{user_id_session}" 
             
            if active:
                params["active"] = 1
                columns_ += ", active"
                values += ", :active"

           
            query = (
                f" INSERT INTO {model_sql.__tablename__} ({columns_}) VALUES ({values})"
            )
            try:
                result = connection.query(query=query, params=params)
                id = result.lastrowid if result else 0
                result = True if result else False
                status_code = 201 if result else 200
                return JSONResponse({"success": result,"id":id}, status_code=status_code)
            except Exception as e:
                print(e)
                Logger.error(f"Error rest_crud_generate , POST: {str(e)}")
                return JSONResponse({"success": False}, status_code=500)

        def search_id(self) -> bool | dict:
            columns = " , ".join(select) if select else "*"
            filters = f"active = 1" if active else ""
            filters += " AND  id =:id" if filters else "  id = :id"
            if "user_id" in model_pydantic.__fields__.keys():
                filters += " AND user_id:user_id"
            elif "id_user" in model_pydantic.__fields__.keys():
                filters += " AND id_user:id_user"


            id = int(self.path_params["id"] )
            params = {"user_id":0,"id":id}

            if user_id_session: 
                user_id=get_user_id_session(self)
                if isinstance(user_id,JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    filters += f" AND {user_id_session} = :{user_id_session}"
                    
            
            
            query = f"SELECT {columns} FROM {model_sql.__tablename__} WHERE {filters} "
            results = connection.query(query=query, params=params,return_row=True)
            return results

        async def get_id(self) -> dict:
            response =await execute_middleware(self,type='get_id')
            if isinstance(response,JSONResponse):
                return response
            item = search_id(self)
            if item is None:
                return JSONResponse({}, status_code=404)
            return JSONResponse(item) if jsonresponse_prefix =='' else JSONResponse({jsonresponse_prefix:item})

        async def put(self):
            response =await execute_middleware(self,type='put')
            if isinstance(response,JSONResponse):
                return response
            result = search_id(self)
            if result is None:
                return JSONResponse({"success": False}, status_code=404)
            result_update = False
            try:
                body = await self.json()
                model = model_pydantic(**body)
            except Exception as e:
                print(str(e))
                return JSONResponse({"success": False, "msg": str(e)}, status_code=400)

            values = (
                "  ".join(f"{row}= :{row}" for row in columns)
                if columns
                else " , ".join(
                    f"{row}=:{row}" for row in list(model_pydantic.__fields__.keys())
                )
            )
            params = {
                field: getattr(model, field)
                for field in model_pydantic.__fields__.keys()
            }

            id = int(self.path_params["id"] )
            params["id"]=id
            if "password" in params:
                params["password"] = ph.hash(params["password"])

            if "token" in params:
                params["token"] = generate_token_value()
            if "hash" in params:
                params["hash"] = generate_token_value()

            filters = ""

            if user_id_session: 
                user_id=get_user_id_session(self)
                if isinstance(user_id,JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    filters += f" AND {user_id_session} = :{user_id_session}"
            
            query = f" UPDATE {model_sql.__tablename__} SET {values} WHERE id= :id {filters}"
            id = self.path_params["id"]
            params["id"] = int(id)
            result = connection.query(query=query, params=params)
            result_update = True if result else False
            return JSONResponse({"success": result_update})

        async def delete(self):
            response =await execute_middleware(self,type='delete')
            if isinstance(response,JSONResponse):
                return response
            result = search_id(self)
            if result is None:
                JSONResponse({"success": False}, status_code=404)

            id = int(self.path_params["id"])
            params = {"id": id, "user_id": 0}
            filters = ""
            if user_id_session: 
                user_id=get_user_id_session(self)
                if isinstance(user_id,JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    filters += f" AND {user_id_session} = :{user_id_session}"

            if delete_logic:
                query = f" UPDATE {model_sql.__tablename__} SET active=0 WHERE id= :id {filters}"
            else:
                query = f"DELETE FROM {model_sql.__tablename__} WHERE id=:id {filters}"

            result = connection.query(query=query, params=params)
            result_delete = True if result else False
            return JSONResponse({"success": result_delete})

        self.routes += [
            Route(path=self.name, name=self.name, methods=["GET"], endpoint=get),
            Route(path=self.name, name=self.name, methods=["POST"], endpoint=post),
            Route(
                path=f"{self.name}/{{id}}",
                name=f"{self.name}_get_id",
                methods=["GET"],
                endpoint=get_id,
            ),
            Route(
                path=f"{self.name}/{{id}}",
                name=f"{self.name}_put",
                methods=["PUT"],
                endpoint=put,
            ),
            Route(
                path=f"{self.name}/{{id}}",
                name=f"{self.name}_delete",
                methods=["DELETE"],
                endpoint=delete,
            ),
        ]

        self.docs.append({"path": self.name, "model": model_pydantic})
        self.docs.append({"path": f"{self.name}/{{id}}", "model": model_pydantic})
