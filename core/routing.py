from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from app.config import TITLE_PROJECT, VERSION_PROJECT, DESCRIPTION_PROJECT
from typing import Any, Type, Optional, List
from pydantic import BaseModel
from argon2 import PasswordHasher
from app.helpers.helpers import generate_token_value, get_user_by_token
from core.logger import Logger
import datetime
import re
from functools import wraps

ph = PasswordHasher()


class Router:
    def __init__(self, prefix: str = "") -> None:
        self.routes = []
        self.docs = []
        self.prefix = prefix

    def route(self, path: str, methods: list[str] = ["GET"], model=None) -> None:
        try:
            real_path = self.normalize_path(prefix=self.prefix, path=path)

            def decorator(func):
                self.routes.append(
                    Route(path=real_path, endpoint=func, methods=methods)
                )
                if model is not None:
                    self.docs.append({"path": real_path, "model": model})

                return func

            return decorator
        except RuntimeError as e:
            Logger.error(f"Error : {str(e)}")
            print(f"Error : {e}")

    def normalize_path(self, prefix: str, path: str) -> str:
        full = f"/{prefix.strip('/')}/{path.strip('/')}"
        return re.sub(r"//+", "/", full)

    def get(self, path: str, **kwargs):
        return self.route(path, methods=["GET"], **kwargs)

    def post(self, path: str, **kwargs):
        return self.route(path, methods=["POST"], **kwargs)

    def put(self, path: str, **kwargs):
        return self.route(path, methods=["PUT"], **kwargs)

    def delete(self, path: str, **kwargs):
        return self.route(path, methods=["DELETE"], **kwargs)

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

    def swagger_ui(
        self,
        path: str = "/docs",
        methods: list[str] | None = None,
        swagger_url: str = "/public/swagger",
    ) -> None:
        if methods is None:
            methods = ["GET"]

        def swagger_docs(request: Request):
            html = f"""
            <html>
            <head>
                <title>API Documentation</title>
                <link rel="stylesheet" type="text/css" href="{swagger_url}/swagger-ui.css" />
                <script src="{swagger_url}/swagger-ui-bundle.js"></script>
                <script src="{swagger_url}/swagger-ui-standalone-preset.js"></script>
            </head>
            <body>
                <div id="swagger-ui"></div>
                <script>
                    const ui = SwaggerUIBundle({{
                        url: '/openapi.json',
                        dom_id: '#swagger-ui',
                        deepLinking: true,
                        presets: [
                            SwaggerUIBundle.presets.apis,
                            SwaggerUIStandalonePreset
                        ],
                        layout: "StandaloneLayout"
                    }});
                </script>
            </body>
            </html>
            """
            return HTMLResponse(html)

        self.routes.append(Route(path=path, endpoint=swagger_docs, methods=methods))

    def openapi_json(self, path: str = "/openapi.json", methods: list[str] | None = None) -> None:
        if methods is None:
            methods = ["GET"]

        def openapi_schema(request: Request):
            openapi_schema = {
                "openapi": "3.0.0",
                "info": {
                    "title": TITLE_PROJECT,
                    "version": VERSION_PROJECT,
                    "description": DESCRIPTION_PROJECT,
                },
                "paths": {},
                "components": {"schemas": {}},
            }

            EXCLUDED = {"/docs", "/openapi.json"}

            for route in self.routes:
                if not isinstance(route, Route):
                    continue

                route_path = route.path
                if route_path in EXCLUDED:
                    continue

                model = None
                for doc in self.docs:
                    doc_path = doc.get("path")
                    if not doc_path:
                        continue
                    route_base = re.sub(r"/\{[^/]+\}", "", route_path)
                    if doc_path.rstrip("/") == route_base.rstrip("/"):
                        model = doc.get("model")
                        break

                model_schema = None
                if model and hasattr(model, "schema"):
                    try:
                        model_schema = model.schema()
                        if model.__name__ not in openapi_schema["components"]["schemas"]:
                            openapi_schema["components"]["schemas"][model.__name__] = model_schema
                    except Exception:
                        model_schema = None

                methods_list = route.methods or ["GET"]
                for method in methods_list:
                    m = method.lower()
                    if m == "head":
                        continue

                    openapi_schema["paths"].setdefault(route_path, {})

                    path_param_names = self.get_path_params(route_path)
                    path_parameters = []
                    for pname in path_param_names:
                        inferred_schema = {"type": "string"}
                        if model_schema:
                            props = model_schema.get("properties", {})
                            if pname in props:
                                prop = props[pname]
                                inferred_schema = {}
                                if "$ref" in prop:
                                    inferred_schema["$ref"] = prop["$ref"]
                                else:
                                    if "type" in prop:
                                        inferred_schema["type"] = prop["type"]
                                    if "format" in prop:
                                        inferred_schema["format"] = prop["format"]
                        path_parameters.append(
                            {"name": pname, "in": "path", "required": True, "schema": inferred_schema}
                        )

                    op = {
                        "summary": route.name or getattr(route.endpoint, "__name__", ""),
                        "parameters": path_parameters,
                        "responses": {
                            "200": {"description": route.endpoint.__doc__ or f"{route.name} function", "content": {}}
                        },
                    }

                    if model_schema and m in ["post", "put", "patch"]:
                        props = dict(model_schema.get("properties", {}))
                        required = list(model_schema.get("required", []))
                        for p in path_param_names:
                            props.pop(p, None)
                            if p in required:
                                required.remove(p)
                        request_schema = {"type": "object", "properties": props}
                        if required:
                            request_schema["required"] = required
                        op["requestBody"] = {"required": True, "content": {"application/json": {"schema": request_schema}}}

                    if model_schema:
                        op["responses"]["200"]["content"] = {
                            "application/json": {"schema": {"$ref": f"#/components/schemas/{model.__name__}"}}
                        }

                    openapi_schema["paths"][route_path][m] = op

            return JSONResponse(openapi_schema)

        self.routes.append(Route(path=path, endpoint=openapi_schema, methods=methods))
        
    def get_path_params(self, path: str):
        return re.findall(r"{(\w+)(?::\w+)?}", path)

    def get_params(self, route):
        model = None
        for doc in self.docs:
            if doc.get("path") == route.path:
                model = doc.get("model")
                break

        if model is None or not hasattr(model, "schema"):
            return {}

        m_schema = model.schema()
        props = m_schema.get("properties", {})
        required = set(m_schema.get("required", []))

        parameters = {}
        for field_name, field_schema in props.items():
            parameters[field_name] = {
                "name": field_name,
                "required": field_name in required,
                "schema": field_schema,
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
        router,
        connection,
        model_sql,
        model_pydantic: Type[BaseModel],
        select: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        active: bool = False,
        delete_logic: bool = False,
        middlewares: dict = None,
        jsonresponse_prefix: str = "",
        user_id_session: bool | str = False,
        base_path: str = None,
    ) -> None:
        name = base_path or f"/api/{model_sql.__tablename__}"
        crud_routes = []

        def middleware(func):
            @wraps(func)
            async def middleware_wr(*args, **kwargs):
                if callable(func):
                    result = func(*args, **kwargs)
                    if hasattr(result, "__await__"):
                        return await result
                    return result

            return middleware_wr

        async def execute_middleware(self, type: str):
            if middlewares is not None and type in middlewares:
                for middleware_get in middlewares[type]:
                    middleware_func = middleware(middleware_get)
                    response = await middleware_func(self)
                    if isinstance(response, JSONResponse):
                        return response

        def get_user_id_session(self):
            id_token = get_user_by_token(self)
            if isinstance(id_token, JSONResponse):
                return id_token
            return id_token

        async def get(self):
            try:
                response = await execute_middleware(self, type="get")
                if isinstance(response, JSONResponse):
                    return response

                columns = " , ".join(select) if select else "*"
                filters = f"WHERE active = 1" if active else ""
                params = {"user_id": 0}
                if user_id_session:

                    user_id = get_user_id_session(self)
                    if isinstance(user_id, JSONResponse):
                        return user_id
                    params[user_id_session] = user_id
                    filters += f" AND {user_id_session}= :{user_id_session}"
                else:
                    params = None

                query = f"SELECT {columns} FROM {model_sql.__tablename__} {filters}"
                items = connection.query(query=query, params=params, return_rows=True)
                return (
                    JSONResponse(items)
                    if jsonresponse_prefix == ""
                    else JSONResponse({jsonresponse_prefix: items})
                )
            except Exception as e:
                Logger.error(f"Error rest crud , GET: {str(e)}")

        async def post(self):
            response = await execute_middleware(self, type="post")
            if isinstance(response, JSONResponse):
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
                user_id = get_user_id_session(self)
                if isinstance(user_id, JSONResponse):
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
                return JSONResponse(
                    {"success": result, "id": id}, status_code=status_code
                )
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

            id = int(self.path_params["id"])
            params = {"user_id": 0, "id": id}

            if user_id_session:
                user_id = get_user_id_session(self)
                if isinstance(user_id, JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    filters += f" AND {user_id_session} = :{user_id_session}"

            query = f"SELECT {columns} FROM {model_sql.__tablename__} WHERE {filters} "
            results = connection.query(query=query, params=params, return_row=True)
            return results

        async def get_id(self) -> dict:
            response = await execute_middleware(self, type="get_id")
            if isinstance(response, JSONResponse):
                return response
            item = search_id(self)
            if item is None:
                return JSONResponse({}, status_code=404)
            return (
                JSONResponse(item)
                if jsonresponse_prefix == ""
                else JSONResponse({jsonresponse_prefix: item})
            )

        async def put(self):
            response = await execute_middleware(self, type="put")
            if isinstance(response, JSONResponse):
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

            id = int(self.path_params["id"])
            params["id"] = id
            if "password" in params:
                params["password"] = ph.hash(params["password"])

            if "token" in params:
                params["token"] = generate_token_value()
            if "hash" in params:
                params["hash"] = generate_token_value()

            filters = ""

            if user_id_session:
                user_id = get_user_id_session(self)
                if isinstance(user_id, JSONResponse):
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
            response = await execute_middleware(self, type="delete")
            if isinstance(response, JSONResponse):
                return response
            result = search_id(self)
            if result is None:
                JSONResponse({"success": False}, status_code=404)

            id = int(self.path_params["id"])
            params = {"id": id, "user_id": 0}
            filters = ""
            if user_id_session:
                user_id = get_user_id_session(self)
                if isinstance(user_id, JSONResponse):
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

        crud_routes += [
            Route(
                path=self.normalize_path(prefix=self.prefix, path=name),
                name=name,
                methods=["GET"],
                endpoint=get,
            ),
            Route(
                path=self.normalize_path(prefix=self.prefix, path=name),
                name=name,
                methods=["POST"],
                endpoint=post,
            ),
            Route(
                path=f"{self.normalize_path(prefix=self.prefix,path=name)}/{{id}}",
                name=f"{name}_get_id",
                methods=["GET"],
                endpoint=get_id,
            ),
            Route(
                path=f"{self.normalize_path(prefix=self.prefix,path=name)}/{{id}}",
                name=f"{name}_put",
                methods=["PUT"],
                endpoint=put,
            ),
            Route(
                path=f"{self.normalize_path(prefix=self.prefix,path=name)}/{{id}}",
                name=f"{name}_delete",
                methods=["DELETE"],
                endpoint=delete,
            ),
        ]
        docs_info = [
            {
                "path": self.normalize_path(prefix=self.prefix, path=name),
                "model": model_pydantic,
            },
            {"path": f"{name}/{{id}}", "model": model_pydantic},
        ]
        router.routes.extend(crud_routes)
        router.docs.extend(docs_info)
