"""Lila Framework v2.0.x High-Performance Router.

- Automatic response casting (dict/list/Pydantic -> JSON, str -> HTML)
- Typed path/query parameter injection with pre-compiled TypeAdapter (Rust-speed) and real 422 validation
- Pydantic v2 body validation with localized errors
- Per-route options: rate_limit, cache, cache_public, csrf, auth, sanitize_xss
- Vary: Accept, X-Lila-Partial, Cookie headers for safe SPA caching
- OpenAPI-friendly metadata and WebSocketHub integration
"""

import hashlib
import inspect
import asyncio
import types
from functools import wraps
from enum import Enum
from typing import (
    Optional,
    Callable,
    Any,
    List,
    Dict,
    Type,
    Union,
    Annotated,
    Literal,
    get_args,
    get_origin,
)

from pydantic import BaseModel as PydanticBaseModel, ValidationError, TypeAdapter
from starlette.routing import Route, WebSocketRoute
from starlette.responses import Response

try:
    import email_validator  # noqa: F401
    from pydantic import EmailStr
except ImportError:
    from pydantic import Field

    EmailStr = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]

from lila.core.request import Request
from lila.core.responses import JSONResponse, HTMLResponse
from lila.core.cache import Cache
from lila.core.csrf import CSRF
from lila.core.security import Security
from lila.core.translate import Translate
from lila.core.session import Session
from lila.core.logger import Logger

# v1-compatible SEO decorator (also available as lila.core.seo.seo).
from lila.core.seo import seo, SEO_CONFIG  # noqa: E402


def _unwrap_annotation(annotation: Any) -> Any:
    """Unwraps Annotated and single-member Optional/Union annotations."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    origin = get_origin(annotation)
    if origin is Union or (hasattr(types, "UnionType") and origin is types.UnionType):
        members = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(members) == 1:
            return _unwrap_annotation(members[0])
    return annotation


def _is_pydantic_model(annotation: Any) -> bool:
    annotation = _unwrap_annotation(annotation)
    return inspect.isclass(annotation) and issubclass(annotation, PydanticBaseModel)


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is Union or (hasattr(types, "UnionType") and origin is types.UnionType):
        return type(None) in get_args(annotation)
    return False


def _cast_param(val: Any, target_type: Type) -> Any:
    """Casts a path/query value according to the handler annotation (backward-compatibility)."""
    if val is None:
        return None
    if target_type in (inspect.Parameter.empty, Any):
        return val

    target = _unwrap_annotation(target_type)
    origin = get_origin(target)
    members = get_args(target)

    if target is str:
        return str(val)
    if target is int:
        if isinstance(val, bool):
            return int(val)
        return int(str(val).strip())
    if target is float:
        return float(str(val).strip())
    if target is bool:
        return str(val).strip().lower() in ("true", "1", "yes", "on")
    if origin is Literal:
        text = str(val)
        if text not in [str(member) for member in members]:
            raise ValueError(f"Input should be one of: {', '.join(str(m) for m in members)}")
        for member in members:
            if str(member) == text:
                return member
        return text
    if isinstance(target, type) and issubclass(target, Enum):
        try:
            return target(val)
        except Exception:
            return target[str(val)]
    if origin in (list, tuple, set):
        inner = members[0] if members else str
        values = val if isinstance(val, (list, tuple, set)) else [val]
        return origin(_cast_param(item, inner) for item in values)  # type: ignore[operator]
    if target is dict:
        return val if isinstance(val, dict) else dict(val)

    try:
        return TypeAdapter(target).validate_python(val)
    except Exception:
        if isinstance(target, type):
            return target(val)
        return val


def _param_error(field: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"success": False, "errors": [{field: message}], "msg": f"{field}: {message}"},
        status_code=422,
    )


class RouteParam:
    """Pre-compiled metadata for a single path/query parameter."""

    __slots__ = (
        "name",
        "annotation",
        "adapter",
        "default",
        "required",
        "is_optional",
        "is_list",
    )

    def __init__(
        self,
        name: str,
        annotation: Any,
        adapter: Optional[TypeAdapter],
        default: Any,
        required: bool,
        is_optional: bool,
        is_list: bool,
    ):
        self.name = name
        self.annotation = annotation
        self.adapter = adapter
        self.default = default
        self.required = required
        self.is_optional = is_optional
        self.is_list = is_list


def _build_param_adapter(annotation: Any) -> Optional[TypeAdapter]:
    """Pre-compiles a Pydantic TypeAdapter once during route registration."""
    if annotation in (inspect.Parameter.empty, Any):
        return None
    try:
        return TypeAdapter(annotation)
    except Exception:
        return None


class RouteInspector:
    """Pre-analyzes route handlers once during registration for fast dispatch."""

    __slots__ = (
        "handler",
        "is_async",
        "sig",
        "has_write_method",
        "wants_request",
        "body_param_name",
        "body_model",
        "body_optional",
        "query_model_name",
        "query_model",
        "path_params",
        "query_params",
        "params_map",
    )

    def __init__(self, handler: Callable, methods: Optional[List[str]] = None):
        self.handler = handler
        self.is_async = inspect.iscoroutinefunction(handler)
        self.sig = inspect.signature(handler)
        methods = [m.upper() for m in (methods or ["GET"])]
        self.has_write_method = any(m in ("POST", "PUT", "PATCH", "DELETE") for m in methods)

        self.wants_request = False
        self.body_param_name: Optional[str] = None
        self.body_model: Optional[Type[PydanticBaseModel]] = None
        self.body_optional = False
        self.query_model_name: Optional[str] = None
        self.query_model: Optional[Type[PydanticBaseModel]] = None
        self.path_params: Dict[str, Type] = {}
        self.query_params: Dict[str, tuple] = {}
        self.params_map: Dict[str, RouteParam] = {}

        for name, param in self.sig.parameters.items():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            ann = param.annotation
            default = param.default
            required = default is inspect.Parameter.empty

            if ann is Request or (name == "request" and not _is_pydantic_model(ann)):
                self.wants_request = True
                continue

            if _is_pydantic_model(ann):
                if not self.has_write_method:
                    # GET-only handlers interpret a Pydantic annotation as a query model.
                    self.query_model_name = name
                    self.query_model = _unwrap_annotation(ann)
                    continue
                self.body_param_name = name
                self.body_model = _unwrap_annotation(ann)
                self.body_optional = _is_optional(ann) or not required
                continue

            unwrapped = _unwrap_annotation(ann) if ann is not inspect.Parameter.empty else str
            is_list = get_origin(unwrapped) in (list, tuple, set)
            adapter = _build_param_adapter(ann if ann is not inspect.Parameter.empty else str)

            route_param = RouteParam(
                name=name,
                annotation=ann,
                adapter=adapter,
                default=None if required else default,
                required=required,
                is_optional=_is_optional(ann),
                is_list=is_list,
            )
            self.params_map[name] = route_param
            self.path_params[name] = unwrapped
            self.query_params[name] = (
                unwrapped,
                None if required else default,
                required,
                _is_optional(ann),
            )


class Router:
    """Ergonomic route collection with FastAPI-style conveniences."""

    def __init__(
        self,
        prefix: str = "",
        tags: Optional[List[str]] = None,
        middlewares: Optional[List[Callable]] = None,
        openapi: bool = True,
        default_cache_ttl: Optional[int] = None,
        cache_cookie_keys: Optional[List[str]] = None,
    ):
        self.prefix = prefix.rstrip("/")
        self.tags = tags or []
        self.middlewares = middlewares or []
        self.openapi = openapi
        self.default_cache_ttl = default_cache_ttl
        self.cache_cookie_keys = cache_cookie_keys or ["session", "auth"]
        self.routes: List[Union[Route, WebSocketRoute]] = []
        self.openapi_routes: List[dict] = []

    def _normalize_path(self, path: str) -> str:
        p = path.strip()
        full = f"{self.prefix}/{p.lstrip('/')}" if self.prefix else p
        if not full.startswith("/"):
            full = f"/{full}"
        return full or "/"

    def get_routes(self) -> List[Union[Route, WebSocketRoute]]:
        return self.routes

    def add_route(
        self,
        path: str,
        handler: Callable,
        methods: List[str],
        name: Optional[str] = None,
        model: Optional[Type[PydanticBaseModel]] = None,
        rate_limit: Optional[Union[int, tuple]] = None,
        cache: Optional[int] = None,
        cache_ttl: Optional[int] = None,
        cache_public: bool = False,
        csrf: bool = False,
        auth: bool = False,
        sanitize_xss: bool = False,
        summary: Optional[str] = None,
        openapi: Optional[bool] = None,
    ) -> None:
        norm_path = self._normalize_path(path)
        methods = [m.upper() for m in methods]
        inspector = RouteInspector(handler, methods=methods)
        active_model = model or inspector.body_model
        body_param_name = inspector.body_param_name
        if cache is None:
            cache = cache_ttl if cache_ttl is not None else self.default_cache_ttl

        wrapped_handler = handler
        for mw in reversed(self.middlewares):
            if callable(mw):
                wrapped_handler = mw(wrapped_handler)
        is_wrapped_async = inspect.iscoroutinefunction(wrapped_handler)

        @wraps(handler)
        async def endpoint_wrapper(request: Request):
            # 1. Rate limiting
            if rate_limit:
                max_req, win = (rate_limit, 60) if isinstance(rate_limit, int) else rate_limit
                client_ip = getattr(request.client, "host", "unknown")
                rl_key = f"rl:r:{handler.__module__}.{handler.__qualname__}:{client_ip}"
                cnt = await Cache.incr_async(rl_key, ttl=int(win))
                if cnt > int(max_req):
                    return JSONResponse(
                        {"success": False, "error": "rate_limit_exceeded", "message": "Rate limit exceeded."},
                        status_code=429,
                        headers={"Retry-After": str(win)},
                    )

            # 2. Auth check
            if auth:
                user = await Session.get_async(request)
                if not user:
                    if request.headers.get("accept", "").lower().startswith("application/json") or request.url.path.startswith("/api/"):
                        return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)
                    from starlette.responses import RedirectResponse

                    return RedirectResponse("/login", status_code=303)
                request.state.user = user

            # 3. Response cache (per identity by default)
            cache_key = None
            if cache and request.method == "GET":
                identity = ""
                if not cache_public:
                    fingerprint_src = f"{request.headers.get('cookie', '')}|{request.headers.get('authorization', '')}"
                    identity = hashlib.sha256(fingerprint_src.encode("utf-8", errors="ignore")).hexdigest()[:16]
                lang = request.headers.get("accept-language", "")[:24]
                cache_key = f"route:{request.method}:{norm_path}:{request.url.query}:{identity}:{lang}"
                cached = await Cache.get_async(cache_key)
                if cached is not None:
                    if isinstance(cached, (dict, list)):
                        cached_res = JSONResponse(cached)
                    elif isinstance(cached, str):
                        cached_res = HTMLResponse(cached)
                    else:
                        cached_res = cached
                    cached_res.headers["Vary"] = "Accept, X-Lila-Partial, Cookie"
                    return cached_res

            # 4. Extract and cast arguments (using pre-compiled TypeAdapter)
            kwargs: Dict[str, Any] = {}
            if inspector.wants_request:
                kwargs["request"] = request

            path_params = request.path_params
            for k, val in path_params.items():
                if k in inspector.params_map:
                    param = inspector.params_map[k]
                    if param.adapter is not None:
                        try:
                            kwargs[k] = param.adapter.validate_python(val)
                        except Exception as err:
                            return _param_error(k, str(err) or "Invalid value")
                    else:
                        kwargs[k] = val
                elif k in inspector.sig.parameters:
                    target_t = inspector.sig.parameters[k].annotation
                    try:
                        kwargs[k] = _cast_param(val, target_t)
                    except (ValueError, TypeError) as err:
                        return _param_error(k, str(err) or "Invalid value")

            query_params = request.query_params
            for qk, param in inspector.params_map.items():
                if qk in kwargs or qk in path_params:
                    continue
                if qk in query_params:
                    try:
                        if param.is_list:
                            raw_val = query_params.getlist(qk)
                        else:
                            raw_val = query_params[qk]

                        if param.adapter is not None:
                            val = param.adapter.validate_python(raw_val)
                        else:
                            val = raw_val

                        if sanitize_xss and isinstance(val, str):
                            val = Security.sanitize_str(val)
                        kwargs[qk] = val
                    except Exception as err:
                        return _param_error(qk, str(err) or "Invalid value")
                elif param.required and not param.is_optional:
                    return _param_error(qk, "Field required")
                elif param.default is not None:
                    kwargs[qk] = param.default
                # Missing optional/None params fall back to the Python default.

            # 5. Body parsing and Pydantic validation
            if active_model is not None:
                content_type = request.headers.get("content-type", "").lower()
                data: Any = {}
                try:
                    if "application/json" in content_type:
                        data = await request.json()
                    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
                        form = await request.form()
                        data = dict(form)
                    elif request.method in ("GET", "HEAD", "DELETE"):
                        data = dict(query_params)
                    else:
                        raw_body = await request.body()
                        if raw_body:
                            try:
                                data = await request.json()
                            except Exception:
                                data = {}
                        else:
                            data = {}

                    if sanitize_xss and data is not None:
                        data = Security.sanitize_data(data)

                    request.state.raw_data = data
                    request.state.data = data
                    validated_body = active_model.model_validate(data)
                    request.state.data = validated_body
                    if body_param_name:
                        kwargs[body_param_name] = validated_body
                except ValidationError as val_err:
                    translated = Translate.format_errors(val_err, request=request)
                    return JSONResponse.validation_error(val_err, translated_errors=translated)
                except Exception as err:
                    return JSONResponse(
                        {"success": False, "message": f"Malformed payload: {str(err)}"}, status_code=400
                    )

            # 6. CSRF verification (after body parsing)
            if csrf and request.method in ("POST", "PUT", "DELETE", "PATCH"):
                if not await CSRF.verify_async(request):
                    return JSONResponse(
                        {"success": False, "message": "Invalid or missing CSRF token"}, status_code=403
                    )

            # 7. Query model (GET only)
            if inspector.query_model is not None and inspector.query_model_name:
                try:
                    query_data = dict(query_params)
                    if sanitize_xss:
                        query_data = Security.sanitize_data(query_data)
                    kwargs[inspector.query_model_name] = inspector.query_model.model_validate(query_data)
                except ValidationError as val_err:
                    translated = Translate.format_errors(val_err, request=request)
                    return JSONResponse.validation_error(val_err, translated_errors=translated)

            # 8. Execute handler
            try:
                if is_wrapped_async:
                    result = await wrapped_handler(**kwargs)
                else:
                    result = wrapped_handler(**kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
            except Exception as e:
                Logger.error(f"Error handling route {norm_path}: {e}", exception=e)
                raise

            # 9. Automatic return value casting
            if isinstance(result, Response):
                final_res = result
            elif isinstance(result, PydanticBaseModel):
                final_res = JSONResponse(result.model_dump())
            elif isinstance(result, (dict, list)):
                final_res = JSONResponse(result)
            elif isinstance(result, str):
                final_res = HTMLResponse(result)
            elif result is None:
                final_res = JSONResponse({"success": True})
            else:
                final_res = JSONResponse(result)

            if cache_key and final_res.status_code == 200:
                final_res.headers["Vary"] = "Accept, X-Lila-Partial, Cookie"
                if isinstance(result, PydanticBaseModel):
                    await Cache.set_async(cache_key, result.model_dump(), ttl=cache)
                elif isinstance(result, (dict, list, str)):
                    await Cache.set_async(cache_key, result, ttl=cache)

            return final_res

        route_obj = Route(norm_path, endpoint=endpoint_wrapper, methods=methods, name=name)
        self.routes.append(route_obj)

        is_in_openapi = openapi if openapi is not None else self.openapi
        if is_in_openapi:
            self.openapi_routes.append({
                "path": norm_path,
                "methods": methods,
                "summary": summary or handler.__name__.replace("_", " ").title(),
                "inspector": inspector,
                "tags": self.tags,
            })

    # Method decorators
    def get(self, path: str, **kwargs):
        def decorator(fn: Callable):
            self.add_route(path, fn, methods=["GET"], **kwargs)
            return fn
        return decorator

    def post(self, path: str, **kwargs):
        def decorator(fn: Callable):
            self.add_route(path, fn, methods=["POST"], **kwargs)
            return fn
        return decorator

    def put(self, path: str, **kwargs):
        def decorator(fn: Callable):
            self.add_route(path, fn, methods=["PUT"], **kwargs)
            return fn
        return decorator

    def delete(self, path: str, **kwargs):
        def decorator(fn: Callable):
            self.add_route(path, fn, methods=["DELETE"], **kwargs)
            return fn
        return decorator

    def patch(self, path: str, **kwargs):
        def decorator(fn: Callable):
            self.add_route(path, fn, methods=["PATCH"], **kwargs)
            return fn
        return decorator

    def route(self, path: Optional[str] = None, methods: Optional[List[str]] = None, **kwargs):
        """v1-compatible alias: ``@router.route('/x', methods=['GET', 'POST'])``."""
        def decorator(fn: Callable):
            self.add_route(path or "/", fn, methods=methods or ["GET"], **kwargs)
            return fn

        # Support ``@router.route`` without parentheses (defaults to GET).
        if callable(path):
            fn = path
            self.add_route("/", fn, methods=methods or ["GET"], **kwargs)
            return fn
        return decorator

    def websocket(self, path: str):
        """Standard Starlette WebSocket route decorator."""
        def decorator(fn: Callable):
            norm_path = self._normalize_path(path)
            self.routes.append(WebSocketRoute(norm_path, endpoint=fn))
            return fn
        return decorator

    ws = websocket

    def ws_hub(self, path: str, hub: Any):
        """Mounts a WebSocketHub automatically on this path."""
        norm_path = self._normalize_path(path)

        async def _endpoint(websocket):
            await hub.handle_connection(websocket)

        self.routes.append(WebSocketRoute(norm_path, endpoint=_endpoint))

    def rest_crud_generate(self, model_sql: Any, base_route: Optional[str] = None, auth: bool = False):
        """Generates clean, full async REST endpoints for an ActiveRecord model."""
        route_name = base_route or model_sql.__tablename__
        route_prefix = f"/{route_name.strip('/')}"

        @self.get(route_prefix, auth=auth)
        async def list_records(request: Request, limit: int = 100, offset: int = 0):
            return await model_sql.get_all_async(limit=limit, offset=offset)

        @self.get(f"{route_prefix}/{{id:int}}", auth=auth)
        async def get_record(request: Request, id: int):
            rec = await model_sql.get_by_id_async(id)
            if not rec:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return rec

        @self.post(route_prefix, auth=auth)
        async def create_record(request: Request):
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"success": False, "message": "Invalid JSON body"}, status_code=400)
            try:
                created = await model_sql.insert_async(**data)
            except Exception as exc:
                return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
            return JSONResponse({"success": True, "data": created}, status_code=201)

        @self.put(f"{route_prefix}/{{id:int}}", auth=auth)
        async def update_record(request: Request, id: int):
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"success": False, "message": "Invalid JSON body"}, status_code=400)
            try:
                ok = await model_sql.update_async(id, **data)
            except Exception as exc:
                return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
            if not ok:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return {"success": True, "id": id}

        @self.delete(f"{route_prefix}/{{id:int}}", auth=auth)
        async def delete_record(request: Request, id: int):
            ok = await model_sql.delete_async(id)
            if not ok:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return {"success": True, "deleted": True}
