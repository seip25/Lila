from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from lila.core.responses import HTMLResponse, JSONResponse, RedirectResponse
from lila.core.request import Request
from app.config import (
    TITLE_PROJECT,
    VERSION_PROJECT,
    DESCRIPTION_PROJECT,
    PATH_TEMPLATES_HTML,
)
from typing import Any, Type, Optional, List
from pydantic import BaseModel, ValidationError
from argon2 import PasswordHasher
from lila.core.auth import generate_token_value, get_user_id_by_token as get_user_by_token
from lila.core.translate import Translate
from lila.core.security import Security
from lila.core.logger import Logger

import datetime
import re
from functools import wraps
from pathlib import Path
from lila.core.templates import render
import asyncio

ph = PasswordHasher()


class Router:
    def __init__(self, prefix: str = "") -> None:
        self.routes = []
        self.docs = []
        self.prefix = prefix

    def route(self, path: str, methods: list[str] = None, model: Type[BaseModel] = None) -> None:
        if methods is None:
            methods = ["GET"]
        
        real_path = self.normalize_path(prefix=self.prefix, path=path)

        def decorator(func):
            @wraps(func)
            async def validation_wrapper(request: Request):
                current_lang=Translate.lang(request=request)
                
                # Check for XSS in query parameters
                if Security.check_xss(str(request.query_params)):
                    return JSONResponse({"success": False, "msg": "Potential XSS detected in query parameters"}, status_code=400)

                if model and request.method in ["POST", "PUT", "PATCH"]:
                    try:
                        body = await request.json()
                        # Sanitize incoming data
                        sanitized_body = Security.sanitize_data(body)
                        
                        # Check for XSS in sanitized body (extra layer)
                        if Security.check_xss(str(sanitized_body)):
                             return JSONResponse({"success": False, "msg": "Potential XSS detected in body"}, status_code=400)

                        validated_data = model(**sanitized_body)
                        request.state.data = validated_data
                    except ValidationError as e:
                        return self.response_validation_error(e,current_lang)
                    except Exception as e:
                        msg = "Invalid JSON Body" if current_lang == "en" else "JSON inválido"
                        if DEBUG:
                            print(f"Routing Error: {e}")
                        return JSONResponse({"success": False, "msg": msg}, status_code=400)
                
                if asyncio.iscoroutinefunction(func):
                    return await func(request)
                return func(request)

            self.routes.append(
                Route(path=real_path, endpoint=validation_wrapper, methods=methods)
            )
            
            if model is not None:
                self.docs.append({"path": real_path, "model": model})

            return func
        return decorator

    def response_validation_error(self, e: ValidationError, language: str="en"):
        errors_list = []
        msg_parts = []
        
        for err in e.errors():
            field = err["loc"][-1] 
            translated_msg = Translate.translate_pydantic_error(err, language)
            
            errors_list.append({str(field): translated_msg})
            msg_parts.append(f"{field}: {translated_msg}")

        return JSONResponse(
            {
                "success": False, 
                "errors": errors_list, 
                "msg": " . ".join(msg_parts)
            },
            status_code=400,
        )

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
        self, path: str = "/public", directory: str = "public", name: str = "public"
    ) -> None:

        try:
            self.routes.append(Mount(path, StaticFiles(directory=directory), name=name))
        except RuntimeError as e:
            Logger.error(f"Error : {str(e)}")
            print(f"Error :{e}")

    def patch(self, path: str, **kwargs):
        return self.route(path, methods=["PATCH"], **kwargs)

    def websocket(self, path: str):
        """Register a WebSocket endpoint."""
        def decorator(func):
            real_path = self.normalize_path(prefix=self.prefix, path=path)
            self.routes.append(WebSocketRoute(path=real_path, endpoint=func))
            return func
        return decorator

    def get_routes(self) -> list:
        return self.routes

    def swagger_ui(
        self,
        path: str = "/docs",
        methods: list[str] | None = None,
        swagger_url: str = "swagger",
        title: str = "Lila API Documentation",
        icon: str = "img/lila.png",
    ) -> None:
        if methods is None:
            methods = ["GET"]

        def swagger_docs(request : Request):
            html = f"""
            <html>
            <head>
                <title>{title}</title>
                  <link rel="icon" type="image/x-icon" href="{icon}" />
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

        self.routes.append(
            Route(
                path=path,
                endpoint=swagger_docs,
                methods=methods,
            )
        )

    def openapi_json(
        self, path: str = "/openapi.json", methods: list[str] | None = None
    ) -> None:
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
                        if (
                            model.__name__
                            not in openapi_schema["components"]["schemas"]
                        ):
                            openapi_schema["components"]["schemas"][
                                model.__name__
                            ] = model_schema
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
                            {
                                "name": pname,
                                "in": "path",
                                "required": True,
                                "schema": inferred_schema,
                            }
                        )

                    op = {
                        "summary": route.name
                        or getattr(route.endpoint, "__name__", ""),
                        "parameters": path_parameters,
                        "responses": {
                            "200": {
                                "description": route.endpoint.__doc__
                                or f"{route.name} function",
                                "content": {},
                            }
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
                        op["requestBody"] = {
                            "required": True,
                            "content": {"application/json": {"schema": request_schema}},
                        }

                    if model_schema:
                        op["responses"]["200"]["content"] = {
                            "application/json": {
                                "schema": {
                                    "$ref": f"#/components/schemas/{model.__name__}"
                                }
                            }
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
        generate_html: bool = True,
        rewrite_tempalte : bool = False,
        url_html : str = None,
    ) -> None:
        name = base_path or f"/{model_sql.__tablename__}"
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
                    if isinstance(response, HTMLResponse) and type == "html":
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
            except ValidationError as e:
                return self.response_validation_error(e)
            except Exception as e:
                Logger.warning(f"Error rest_crud_generate - POST: {str(e)}")
                return JSONResponse(
                    {"success": False, "msg": "Error general"}, status_code=500
                )
            columns_ = (
                " , ".join(columns)
                if columns
                else " , ".join(
                    (row) for row in list(model_pydantic.model_fields.keys())
                )
            )
            values = (
                " , ".join(f":{row}" for row in columns)
                if columns
                else " , ".join(
                    f":{row}" for row in list(model_pydantic.model_fields.keys())
                )
            )
            params = {
                field: getattr(model, field)
                for field in model_pydantic.model_fields.keys()
            }
            if "token" in params:
                params["token"] = generate_token_value()
            if "hash" in params:
                params["hash"] = generate_token_value()

            if "password" in params:
                if params["password"]:
                    params["password"] = ph.hash(params["password"])
                else:
                    del params["password"]

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

           
            try:
                instance=model_sql(**params)
                session = connection.get_session()
                id =connection.query_orm(model=model_sql, operation="insert", instance=instance, session=session)
                result = True if id else False
                status_code = 201 if result else 200
                return JSONResponse(
                    {"success": result, "id": id}, status_code=status_code
                )
            except Exception as e:
                print(e)
                Logger.error(f"Error rest_crud_generate , POST: {str(e)}")
                return JSONResponse({"success": False}, status_code=500)
            
        def search_id(self) -> bool | dict:
            columns_ = " , ".join(select) if select else "*"
            filters = "active = 1" if active else ""
            filters += " AND id = :id" if filters else "id = :id"
            if "user_id" in model_pydantic.model_fields.keys():
                filters += " AND user_id = :user_id"
            elif "id_user" in model_pydantic.model_fields.keys():
                filters += " AND id_user = :id_user"

            id = int(self.path_params["id"])
            params = {"user_id": 0, "id": id}

            if user_id_session:
                user_id = get_user_id_session(self)
                if isinstance(user_id, JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    filters += f" AND {user_id_session} = :{user_id_session}"

            query = f"SELECT {columns_} FROM {model_sql.__tablename__} WHERE {filters}"
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
            except ValidationError as e:
                return self.response_validation_error(e)

            values = (
                " , ".join(f"{row} = :{row}" for row in columns)
                if columns
                else " , ".join(
                    f"{row} = :{row}" for row in list(model_pydantic.model_fields.keys())
                )
            )
            params = {
                field: getattr(model, field)
                for field in model_pydantic.model_fields.keys()
            }

            id = int(self.path_params["id"])
            params["id"] = id
            if "password" in params:
                if params["password"]:
                    params["password"] = ph.hash(params["password"])
                else:
                    del params["password"]

            if "token" in params:
                params["token"] = generate_token_value()
            if "hash" in params:
                params["hash"] = generate_token_value()

            orm_filters = {"id": int(self.path_params["id"])}

            if user_id_session:
                user_id = get_user_id_session(self)
                if isinstance(user_id, JSONResponse):
                    return user_id
                if user_id is not None:
                    params[user_id_session] = user_id
                    orm_filters[user_id_session] = user_id

            try:
                session = connection.get_session()
                result = connection.query_orm(
                    model=model_sql, operation="update",
                    session=session, filters=orm_filters, values=params
                )
                result_update = True if result else False
                return JSONResponse({"success": result_update})
            except Exception as e:
                Logger.error(f"Error rest_crud_generate , PUT: {str(e)}")
                return JSONResponse({"success": False}, status_code=500)

        async def delete(self):
            response = await execute_middleware(self, type="delete")
            if isinstance(response, JSONResponse):
                return response
            result = search_id(self)
            if result is None:
                return JSONResponse({"success": False}, status_code=404)

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
        if generate_html:
            columns_html = list(model_pydantic.model_fields.keys())
            self.generate_html_template(
                model_name=model_sql.__tablename__,
                columns=columns_html,
                prefix_path=self.prefix,
                rewrite_tempalte = rewrite_tempalte
            )

            async def funcHtml(request: Request):
                if middlewares and "html" in middlewares:
                    for mw in middlewares["html"]:
                        if hasattr(mw, "__call__") and not asyncio.iscoroutinefunction(
                            mw
                        ):

                            @mw
                            async def dummy(req):
                                return None

                            result = await dummy(request)
                        else:
                            result = await mw(request)
                        if isinstance(result, (JSONResponse, HTMLResponse, RedirectResponse)):
                            return result

                response = render(
                    request=request, template=f"{model_sql.__tablename__}/index"
                )
                return response

            name_html = f"/{model_sql.__tablename__}/view" if url_html is None else url_html  
            router.routes.append(
                    Route(
                        path=name_html,
                        name=f"{name}_html",
                        methods=["GET"],
                        endpoint=funcHtml,
                    ) 
            )

    def generate_html_template(self, model_name, columns, prefix_path="",rewrite_tempalte : bool=False):
        template_path = Path(PATH_TEMPLATES_HTML) / model_name / "index.html"
        template_path.parent.mkdir(parents=True, exist_ok=True)
        sensitive_fields = {"password", "active", "token", "hash"}
        cols_js = ",\n      ".join(
            [f"{{ key: '{c}', title: '{c.capitalize()}' }}" for c in columns if c not in sensitive_fields]
        )
        url = f"{prefix_path}/{model_name}".replace("//", "/")

        template_content = f"""<!DOCTYPE html>
<html lang="{{{{ lang }}}}" class="light">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light dark" />
    <meta http-equiv="X-UA-Compatible" content="ie=edge" />
    <title>{model_name.capitalize()} CRUD</title>
    <link rel="icon" type="image/x-icon" href="img/lila.png" />
    <link rel="stylesheet" href="css/lila.css" />
    <script src="js/utils.js"></script>
    </head>
    <body>
    <header class="shadow">
    <nav class="container">
       <h2 class="mt-4 mb-4">{model_name.capitalize()} CRUD</h2>
    </nav>
    </header>
    <main class="container mt-4">
     
    <div class="flex justify-between items-center mb-4">
        <button id="create-btn" class="mb-4" onclick="openDialog('{{{{translate['Create']}}}}')">{{{{translate['Create']}}}}</button>
        <button class="mb-4 outline" onclick="fetchData{model_name}()">{{{{translate['Refresh']}}}}</button>
    </div>

    <div id="datatable-container"></div>
    
    <dialog id="crud-dialog" class="p-4 rounded w-full max-w-md">
       <article>
         <h2 id="crud-title" class="text-xl font-semibold mb-4"> </h2>
        <form id="crud-form" method="dialog" class="space-y-4">
            {''.join(f'<div><label class="block text-sm">{c.capitalize()}</label><input name="{c}" class="w-full p-2 border rounded"/></div>' for c in columns)}

            <div class="text-right mt-4" id="form_messages">
            </div>
            <div class="flex justify-end gap-4 space-x-2">
            <button type="button" id="cancel-btn" class="ghost">{{{{translate['Cancel']}}}}</button>
            <button type="submit" >{{{{translate['Save']}}}}</button>
            </div>
        </form>
       </article>
    </dialog>

    </main>

      <footer class="bg-surface py-4 mt-auto">
     
      <div class="container mx-auto px-4 flex justify-between items-center">
        <a
          href="/set-language/es"
          class="underline"
        >
          Español (Esp)
        </a>
        <a
          href="/set-language/en"
           class="underline"
        >
          English (US)
        </a>
      </div>
    </footer>

    <script>
        const dt = new ResponsiveDataTable('datatable-container', {{
        columns: [
            {cols_js}
        ],
        edit: onEdit{model_name},
        delete: onDelete{model_name}
        }});

        async function fetchData{model_name}() {{
        const res = await fetch('/{url}');
        const data = await res.json();
        dt.updateData(data);
        }}

        fetchData{model_name}();

        function onEdit{model_name}(e, id) {{
        openDialog('{{{{translate['Edit']}}}}', id); 
        fetch(`/{url}/${{id}}`).then(r=>r.json()).then(d=>{{
            for(const k in d)  document.querySelector(`[name="${{k}}"]`) ? document.querySelector(`[name="${{k}}"]`).value = d[k] || '' : '';
        }});
        }}

        function onDelete{model_name}(e, id) {{
        if(confirm('{{{{translate['Are you sure you want to delete this item?']}}}}')) {{
            fetch(`/{url}/${{id}}`, {{method: 'DELETE'}}).then(fetchData{model_name});
        }}
        }}

        function openDialog(mode, id=null) {{
        const dialog = document.getElementById('crud-dialog');
        document.getElementById('crud-title').textContent = mode  ;
        document.getElementById('crud-form').reset();
        const form_messages = document.getElementById('form_messages');
        form_messages.innerHTML = '';
        dialog.showModal();
        document.getElementById('crud-form').onsubmit = async (ev) => {{
            ev.preventDefault();
            const form_messages = document.getElementById('form_messages');
            form_messages.innerHTML = '';
            const data = Object.fromEntries(new FormData(ev.target));
            const url = id ? `/{url}/${{id}}` : '/{url}';
            const method = id ? 'PUT' : 'POST';
            const response=await fetch(url, {{method, headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(data)}});
            let msg = '';

            if(!response.ok) {{
                const err = await response.json();
                if (err.errors){{
                    for(const e of err.errors) {{
                        for(const k in e) {{
                            msg += `<p class="text-red-600">${{k}} : ${{e[k]}}</p>`;
                        }}
                    }}
                    form_messages.innerHTML = msg;
                }}
                else{{
                  msg=err.msg || '{{{{translate['Error occurred']}}}} '+ response.status;
                form_messages.innerHTML = `<p class="text-red-600">${{msg}}</p>`;
                }}
                return;
            }}
            const result = await response.json();
            if(result.errors){{
                for(const e of result.errors) {{
                    for(const k in e) {{
                        msg += `<p class="text-red-600">${{k}} : ${{e[k]}}</p>`;
                    }}
                }}
                form_messages.innerHTML = msg;
              
            }}
            else{{
                msg= result.msg || '{{{{translate['Operation failed']}}}}';
                if(!result.success) {{
                    form_messages.innerHTML = `<p class="text-red-600">${{msg}}</p>`;
                    return;
                }}
                else {{
                msg =result.msg || '{{{{translate['Operation successful']}}}}'
                form_messages.innerHTML = `<p class="text-green-600">${{msg}}</p>`;
                ev.target.reset();
                    fetchData{model_name}();
                }}
           }} 
        
        }};
        }}

        document.getElementById('cancel-btn').onclick = () => {{
        document.getElementById('crud-dialog').close();
        }};
    </script>

    </body>
    </html>"""

        if not template_path.exists() or rewrite_tempalte:
            template_path.write_text(template_content,encoding="utf-8")
