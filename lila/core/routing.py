from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from lila.core.responses import HTMLResponse, JSONResponse, RedirectResponse
from lila.core.request import Request
from app.config import (
    TITLE_PROJECT,
    VERSION_PROJECT,
    DESCRIPTION_PROJECT,
    PATH_TEMPLATES_HTML,
    LANG_DEFAULT,
)
from typing import Any, Type, Optional, List
from pydantic import BaseModel, ValidationError
from argon2 import PasswordHasher
from lila.core.auth import generate_token_value, get_user_id_by_token as get_user_by_token
from lila.core.translate import Translate
from lila.core.security import Security
from lila.core.logger import Logger
from lila.core.cache import Cache

import datetime
import re
import os
from functools import wraps
from pathlib import Path
from lila.core.templates import render
from app.config import DEBUG
import asyncio
import importlib.util
import inspect
import pydantic

ph = PasswordHasher()

class CachedStaticFiles(StaticFiles):
    """
    English: Custom StaticFiles that sets Cache-Control headers.
    Español: StaticFiles personalizado que establece cabeceras Cache-Control.
    """
    def __init__(self, *args, cache_timeout: int = 31536000, **kwargs):
        self.cache_timeout = cache_timeout
        super().__init__(*args, **kwargs)

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        if not DEBUG:
            response.headers["Cache-Control"] = f"public, max-age={self.cache_timeout}, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


def seo(
    title: Any = None,
    description: Any = None,
    keywords: Any = None,
    og: dict = None,
    canonical: Any = None,
    author: Any = None,
    robots: Any = None,
    **kwargs
) -> Any:
    """
    English: Decorator to attach SEO metadata to a route handler.
    Español: Decorador para adjuntar metadatos SEO a un manejador de ruta.
    """
    def decorator(func):
        if not hasattr(func, "_seo"):
            func._seo = {}
        if title is not None: func._seo['title'] = title
        if description is not None: func._seo['description'] = description
        if keywords is not None: func._seo['keywords'] = keywords
        if og is not None: func._seo['og'] = og
        if canonical is not None: func._seo['canonical'] = canonical
        if author is not None: func._seo['author'] = author
        if robots is not None: func._seo['robots'] = robots
        for k, v in kwargs.items():
            func._seo[k] = v
        return func
    return decorator


def locales(languages: list[str]) -> Any:
    """
    English: Decorator to enable localized routing. Registers the route for each language path prefix and dynamically sets the active language.
    Español: Decorador para habilitar el enrutamiento localizado. Registra la ruta para cada prefijo de idioma y establece dinámicamente el idioma activo.
    """
    def decorator(func):
        func._locales = languages
        return func
    return decorator


class Router:
    def __init__(self, prefix: str = "", default_cache_ttl: int = 30, cache_cookie_keys: list[str] = None, middlewares: list = None) -> None:
        """
        English: Initializes the router with a prefix, default cache TTL, custom cache cookie keys, and optional router-level middlewares.
        Español: Inicializa el router con un prefijo, un TTL de caché por defecto, claves de cookie personalizadas y middlewares opcionales a nivel de router.
        """
        self.routes = []
        self.docs = []
        self.seo_data = {}
        self.prefix = prefix
        self.default_cache_ttl = default_cache_ttl
        self.cache_cookie_keys = cache_cookie_keys if cache_cookie_keys is not None else ["session", "auth", "auth_admin"]
        self.middlewares = middlewares if middlewares is not None else []
        self._load_centralized_seo()

    def _load_centralized_seo(self) -> None:
        """
        English: Loads centralized SEO configuration from app/seo.py if it exists.
        Español: Carga la configuración SEO centralizada de app/seo.py si existe.
        """
        try:
            # English: Dynamic import to avoid circular dependency and handle optional file.
            # Español: Importación dinámica para evitar dependencia circular y manejar archivo opcional.
       
            spec = importlib.util.spec_from_file_location("app.seo", os.path.join(os.getcwd(), "app", "seo.py"))
            if spec and spec.loader:
                seo_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(seo_module)
                if hasattr(seo_module, "SEO_CONFIG"):
                    self.seo_data.update(seo_module.SEO_CONFIG)
        except Exception:
            pass

    def route(self, path: str, methods: list[str] = None, model: Type[BaseModel] = None, cache_ttl: Optional[int] = None, cache_cookie_keys: Optional[list[str]] = None) -> None:
        if methods is None:
            methods = ["GET"]
        
        real_path = self.normalize_path(prefix=self.prefix, path=path)
        ttl = cache_ttl if cache_ttl is not None else self.default_cache_ttl
        cookie_keys = cache_cookie_keys if cache_cookie_keys is not None else self.cache_cookie_keys

        def decorator(func):
            """
            English: Registers the route and merges SEO metadata.
            Español: Registra la ruta y fusiona los metadatos SEO.
            """
            current_func = func
            for m in reversed(self.middlewares):
                current_func = m(current_func)

            # Inspect signature to auto-detect Pydantic validation parameters
            body_param_name = None
            body_model_class = None
            try:
                sig = inspect.signature(func)
                for param_name, param in sig.parameters.items():
                    if param_name != "request" and inspect.isclass(param.annotation) and issubclass(param.annotation, pydantic.BaseModel):
                        body_param_name = param_name
                        body_model_class = param.annotation
                        break
            except Exception:
                pass

            if hasattr(func, "_seo"):
                current_seo = self.seo_data.get(real_path, {})
                for k, v in func._seo.items():
                    if k not in current_seo or DEBUG:
                        current_seo[k] = v
                self.seo_data[real_path] = current_seo

            @wraps(func)
            async def validation_wrapper(request: Request):
                """
                English: Validation wrapper for route handlers that dynamically matches and sets the active language from the route path or query parameters.
                Español: Wrapper de validación para manejadores de ruta que coincide y establece dinámicamente el idioma activo desde la ruta o parámetros de consulta.
                """
                lang_param = None
                for param_name in ["lang", "changeLang", "change_lang"]:
                    if param_name in request.query_params:
                        lang_param = request.query_params[param_name]
                        break
                
                if lang_param:
                    from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
                    parsed = urlparse(str(request.url))
                    query_dict = parse_qs(parsed.query)
                    for k in ["lang", "changeLang", "change_lang"]:
                        query_dict.pop(k, None)
                    new_query = urlencode(query_dict, doseq=True)
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                    
                    response = RedirectResponse(url=clean_url)
                    await Translate.set_lang(request, response, lang_param)
                    return response

                matched_lang = None
                for lang in getattr(func, "_locales", []):
                    if request.url.path == f"/{lang}" or request.url.path.startswith(f"/{lang}/"):
                        matched_lang = lang
                        break
                
                if matched_lang:
                    request.state.lang = matched_lang

                current_lang = Translate.lang(request=request)
                
                seo_meta = self.seo_data.get(real_path, {})
                if DEBUG and hasattr(func, "_seo"):
                    seo_meta = {**seo_meta, **func._seo}

                request.state.seo = self._process_seo_metadata(seo_meta, current_lang, request)

                session_cookie = ""
                for key in cookie_keys:
                    val = request.cookies.get(key)
                    if val:
                        session_cookie = val
                        break
                        
                auth_header = request.headers.get("Authorization", "")
                
                cache_key = None
                if ttl > 0 and request.method == "GET" and not DEBUG:
                    cache_key = f"route:{request.method}:{request.url.path}:{str(request.query_params)}:{current_lang}:{session_cookie}:{auth_header}"
                    cached_data = Cache.get(cache_key)
                    if cached_data:
                        from starlette.responses import Response
                        return Response(
                            content=cached_data["body"],
                            status_code=cached_data["status_code"],
                            headers=cached_data["headers"],
                            media_type=cached_data["media_type"]
                        )

                if request.query_params and Security.check_xss(str(request.query_params)):
                    return JSONResponse({"success": False,"message": "Potential XSS detected in query parameters", "msg": "Potential XSS detected in query parameters"}, status_code=400)

                target_model = body_model_class or model
                validated_data = None
                if target_model and request.method in ["POST", "PUT", "PATCH"]:
                    try:
                        body = await request.json()
                        sanitized_body = Security.sanitize_data(body)
                        
                        if Security.check_xss(str(sanitized_body)):
                             return JSONResponse({"success": False,"message":"Potential XSS detected in body", "msg": "Potential XSS detected in body"}, status_code=400)

                        validated_data = target_model(**sanitized_body)
                        request.state.data = validated_data
                    except ValidationError as e:
                        return self.response_validation_error(e, current_lang)
                    except Exception as e:
                        msg = "Invalid JSON Body" if current_lang == "en" else "JSON inválido"
                        if DEBUG:
                            print(f"Routing Error: {e}")
                        return JSONResponse({"success": False, "message": msg, "msg": msg}, status_code=400)
                
                kwargs = {}
                if body_param_name and validated_data is not None:
                    kwargs[body_param_name] = validated_data

                if asyncio.iscoroutinefunction(current_func):
                    response = await current_func(request, **kwargs)
                else:
                    response = current_func(request, **kwargs)

                if ttl > 0 and request.method == "GET" and not DEBUG and cache_key:
                    if hasattr(response, "status_code") and response.status_code == 200:
                        if hasattr(response, "body"):
                            cache_data = {
                                "body": response.body,
                                "status_code": response.status_code,
                                "headers": {k.decode('utf-8'): v.decode('utf-8') for k, v in response.raw_headers if k.lower() != b"content-length"},
                                "media_type": getattr(response, "media_type", None)
                            }
                            Cache.set(cache_key, cache_data, ttl=ttl)
                
                return response

            paths_to_register = [real_path]
            for lang in getattr(func, "_locales", []):
                loc_path = f"/{lang}" if real_path == "/" else f"/{lang}/{real_path.lstrip('/')}"
                paths_to_register.append(self.normalize_path("", loc_path))

            for p in paths_to_register:
                self.routes.append(
                    Route(path=p, endpoint=validation_wrapper, methods=methods)
                )
                if model is not None:
                    self.docs.append({"path": p, "model": model})

            return func
        return decorator

    def _process_seo_metadata(self, seo_meta: dict, lang: str, request: Request) -> dict:
        """
        English: Processes SEO metadata resolving translations and language-specific values.
        Español: Procesa los metadatos SEO resolviendo traducciones y valores específicos de idioma.
        """
        processed = {}
        for key, value in seo_meta.items():
            if isinstance(value, dict):
                # English: Multilingual dict support: {"es": "...", "en": "..."}
                # Español: Soporte para dict multilingüe: {"es": "...", "en": "..."}
                processed[key] = value.get(lang, value.get(LANG_DEFAULT, next(iter(value.values())) if value else ""))
            elif isinstance(value, str) and value.startswith("translate:"):
                # English: Translation key support: "translate:home_title"
                # Español: Soporte para clave de traducción: "translate:home_title"
                key_name = value.replace("translate:", "")
                translations = Translate.get_translations("translations", request, lang_default=lang)
                processed[key] = translations.get(key_name, key_name)
            else:
                processed[key] = value
        return processed

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
                "message": " . ".join(msg_parts),
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
        self, path: str = "/public", directory: str = "public", name: str = "public", cache_timeout: int = 31536000
    ) -> None:

        try:
            self.routes.append(Mount(path, CachedStaticFiles(directory=directory, cache_timeout=cache_timeout), name=name))
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
            # English: Cache handling for openapi schema.
            # Español: Manejo de caché para el esquema openapi.
            if not DEBUG:
                cached_openapi = Cache.get("openapi_schema_json")
                if cached_openapi:
                    return JSONResponse(cached_openapi)

            openapi_schema_data = {
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
                            not in openapi_schema_data["components"]["schemas"]
                        ):
                            openapi_schema_data["components"]["schemas"][
                                model.__name__
                            ] = model_schema
                    except Exception:
                        model_schema = None

                methods_list = route.methods or ["GET"]
                for method in methods_list:
                    m = method.lower()
                    if m == "head":
                        continue

                    openapi_schema_data["paths"].setdefault(route_path, {})

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

                    openapi_schema_data["paths"][route_path][m] = op

            if not DEBUG:
                Cache.set("openapi_schema_json", openapi_schema_data, ttl=3600)

            return JSONResponse(openapi_schema_data)

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
                    {"success": False, "message": "Error general", "msg": "Error general"}, status_code=500
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
        template_path = Path(PATH_TEMPLATES_HTML) / model_name / "index.jinja"
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
    <link rel="icon" type="image/x-icon" href="/img/lila.png" />
    {{{{ asset('css/tailwind.css', force_static=True) | safe }}}}
    {{{{ asset('js/utils.js', force_static=True) | safe }}}}
    </head>
    <body class="bg-bg-body dark:bg-bg-body-dark text-slate-850 dark:text-slate-200 min-h-screen flex flex-col font-sans transition-colors duration-300">
    <header class="bg-surface dark:bg-surface-dark border-b border-slate-200 dark:border-slate-800 py-4 shadow-sm">
      <nav class="max-w-6xl mx-auto px-4 flex justify-between items-center">
         <h2 class="text-xl font-black bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">{model_name.capitalize()} CRUD</h2>
         <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Resource Scaffold</span>
      </nav>
    </header>
    
    <main class="max-w-6xl w-full mx-auto px-4 py-8 flex-1">
      <div class="flex justify-between items-center mb-6">
          <button id="create-btn" onclick="openDialog('{{{{translate['Create']}}}}')" class="px-5 py-2.5 bg-primary hover:bg-primary-dark text-white font-bold rounded-xl shadow-material hover:shadow-material-lg transform hover:-translate-y-0.5 transition-all duration-200 text-sm cursor-pointer flex items-center gap-1.5">
            <span>➕</span> {{{{translate['Create']}}}}
          </button>
          <button onclick="fetchData{model_name}()" class="px-5 py-2.5 bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-bold rounded-xl shadow-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-all text-sm cursor-pointer flex items-center gap-1.5">
            <span>🔄</span> {{{{translate['Refresh']}}}}
          </button>
      </div>

      <div id="datatable-container" class="bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-material overflow-x-auto"></div>
      
      <dialog id="crud-dialog" class="p-6 rounded-2xl w-full max-w-md bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-850 shadow-material-lg backdrop:bg-slate-900/40 backdrop:backdrop-blur-sm">
         <div class="flex flex-col gap-6">
           <h3 id="crud-title" class="text-2xl font-black text-slate-850 dark:text-slate-100 tracking-tight"></h3>
           
           <form id="crud-form" method="dialog" class="space-y-4">
              {''.join(f'<div><label class="block text-sm font-bold text-slate-600 dark:text-slate-400 mb-2">{c.capitalize()}</label><input name="{c}" class="w-full px-4 py-2.5 bg-slate-50 dark:bg-slate-900 border border-slate-205 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-slate-800 dark:text-slate-100"/></div>' for c in columns if c not in sensitive_fields)}

              <div id="form_messages" class="text-xs font-semibold pt-1"></div>
              
              <div class="flex justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-850">
                <button type="button" id="cancel-btn" class="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-bold rounded-xl transition-all text-xs cursor-pointer">
                  {{{{translate['Cancel']}}}}
                </button>
                <button type="submit" class="px-4 py-2 bg-primary hover:bg-primary-dark text-white font-bold rounded-xl shadow-material hover:shadow-material-lg transition-all text-xs cursor-pointer">
                  {{{{translate['Save']}}}}
                </button>
              </div>
           </form>
         </div>
      </dialog>
    </main>

    <footer class="bg-surface dark:bg-surface-dark border-t border-slate-200 dark:border-slate-800 py-6 transition-colors duration-300 mt-auto">
      <div class="max-w-6xl mx-auto px-4 flex justify-center gap-2">
        <a href="?lang=es" class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-surface dark:bg-surface-dark hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold transition-all shadow-sm flex items-center gap-1">
          <span>🇪🇸</span> Español
        </a>
        <a href="?lang=en" class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-surface dark:bg-surface-dark hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold transition-all shadow-sm flex items-center gap-1">
          <span>🇺🇸</span> English
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
                            msg += `<p class="text-red-500">${{k}} : ${{e[k]}}</p>`;
                        }}
                    }}
                    form_messages.innerHTML = msg;
                }}
                else{{
                  msg=err.msg || '{{{{translate['Error occurred']}}}} '+ response.status;
                form_messages.innerHTML = `<p class="text-red-500">${{msg}}</p>`;
                }}
                return;
            }}
            const result = await response.json();
            if(result.errors){{
                for(const e of result.errors) {{
                    for(const k in e) {{
                        msg += `<p class="text-red-500">${{k}} : ${{e[k]}}</p>`;
                    }}
                }}
                form_messages.innerHTML = msg;
              
            }}
            else{{
                msg= result.msg || '{{{{translate['Operation failed']}}}}';
                if(!result.success) {{
                    form_messages.innerHTML = `<p class="text-red-500">${{msg}}</p>`;
                    return;
                }}
                else {{
                msg =result.msg || '{{{{translate['Operation successful']}}}}'
                form_messages.innerHTML = `<p class="text-green-500">${{msg}}</p>`;
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
