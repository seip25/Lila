from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from core.env import TITLE_PROJECT, VERSION_PROJECT, DESCRIPTION_PROJECT
from typing import Any, Type, Optional, List
from pydantic import BaseModel
from argon2 import PasswordHasher
from core.helpers import generate_token_value
import datetime

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
            print(f"Error : {e}")

    def mount(
        self, path: str = "/public", directory: str = "static", name: str = "static"
    ) -> None:

        try:
            self.routes.append(Mount(path, StaticFiles(directory=directory), name=name))
        except RuntimeError as e:
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
                                        "description": route.endpoint.__doc__
                                        or f"{route.name} function"
                                    }
                                },
                            }
            return JSONResponse(openapi_schema)

        self.routes.append(Route(path=path, endpoint=openapi_schema, methods=methods))

    def get_params(self, route):
        model = None
        parameters = {}
        for doc in self.docs:
            if doc["path"] == route.path:
                model = doc["model"]

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
    ) -> None:
        self.name = f"/api/{model_sql.__tablename__}"

        def get(self):
            columns = " , ".join(select) if select else "*"
            filters = f"WHERE active = 1" if active else ""
            query = f"SELECT {columns} FROM {model_sql.__tablename__} {filters}"
            results = connection.query(query=query)
            items = results.fetchall() if results else []
            items = [dict(getattr(row, "_mapping",{})) for row in items]
            return JSONResponse(items)

        async def post(self):
            try:
                body = await self.json()
                model = model_pydantic(**body)
            except Exception as e:
                print(str(e))
                return JSONResponse({"success": False}, status_code=400)
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

            if active:
                params["active"] = 1
                columns_ += ", active"
                values += ", :active"

            query = (
                f" INSERT INTO {model_sql.__tablename__} ({columns_}) VALUES ({values})"
            )
            try:
                result = connection.query(query=query, params=params)
                result = True if result else False
                status_code = 201 if result else 200
                return JSONResponse({"success": result}, status_code=status_code)
            except Exception as e:
                print(e)
                return JSONResponse({"success": False}, status_code=500)

        def search_id(self) -> bool | dict:
            columns = " , ".join(select) if select else "*"
            filters = f"active = 1" if active else ""
            filters += " AND  id =:id" if filters else "  id = :id"
            if "user_id" in model_pydantic.__fields__.keys():
                filters += " AND user_id:user_id"
            elif "id_user" in model_pydantic.__fields__.keys():
                filters += " AND id_user:id_user"

            id = self.path_params["id"] or self.query_params["id"]
            params = {"id": int(id)}

            if (
                "user_id" in model_pydantic.__fields__.keys()
                or "user_id" in self.query_params
            ):
                params["user_id"] = self.query_params["user_id"]
                filters += " AND user_id = :user_id"

            elif (
                "id_user" in model_pydantic.__fields__.keys()
                or "id_user" in self.query_params
            ):
                params["id_user"] = self.query_params["id_user"]
                filters += " AND id_user = :id_user"
            query = f"SELECT {columns} FROM {model_sql.__tablename__} WHERE {filters} "
            results = connection.query(query=query, params=params)
            return results

        def get_id(self) -> dict:
            result = search_id(self)
            row = result.fetchone() if result else None
            item = dict(getattr(row, "_mapping", {}))
            return JSONResponse(item)

        async def put(self):
            result = search_id(self)
            if result is not None:
                JSONResponse({"success": False})

            result_update = False
            try:
                body = await self.json()
                model = model_pydantic(**body)
            except Exception as e:
                print(str(e))
                return JSONResponse({"success": False}, status_code=400)

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
            if "password" in params:
                params["password"] = ph.hash(params["password"])

            query = f" UPDATE {model_sql.__tablename__} SET {values} WHERE id:id"
            id = self.path_params["id"]
            params["id"] = int(id)
            result = False
            print(query)
            # result = connection.query(query=query, params=params)
            return JSONResponse({"success": result_update})

        def delete(self):
            return True

        # self.docs.append({"path": self.name, "model": model_pydantic})
        # self.docs.append(
        #     {"path": f"{self.name}/{{id:int}}", "model": model_pydantic}
        # )
        self.routes += [
            Route(path=self.name, name=self.name, methods=["GET"], endpoint=get),
            Route(path=self.name, name=self.name, methods=["POST"], endpoint=post),
            Route(
                path=f"{self.name}/{{id:int}}",
                name=f"{self.name}_get_id",
                methods=["GET"],
                endpoint=get_id,
            ),
            Route(
                path=f"{self.name}/{{id:int}}",
                name=f"{self.name}_put",
                methods=["PUT"],
                endpoint=put,
            ),
            Route(
                path=f"{self.name}/{{id:int}}",
                name=f"{self.name}_delete",
                methods=["DELETE"],
                endpoint=delete,
            ),
        ]
