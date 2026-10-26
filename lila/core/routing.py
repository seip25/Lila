"""Lila Framework v2.0.0 High-Performance Router.
Features:
- Automatic response casting (Dict/List/Pydantic -> JSONResponse, str -> HTMLResponse)
- Automatic Path and Query parameter type injection
- Pydantic v2 Request body validation with instant translated errors
- Per-route declarative options (rate_limit, cache, csrf, auth)
- WebSocketHub integration
- Clean REST CRUD generator using BaseModel
- OpenAPI 3.0 schema generation
"""

import inspect
import asyncio
from functools import wraps
from typing import Optional, Callable, Any, List, Dict, Type, Union

from starlette.routing import Route, WebSocketRoute
from starlette.responses import Response
from starlette.types import ASGIApp
from typing import Annotated
from pydantic import BaseModel as PydanticBaseModel, ValidationError, Field

try:
    import email_validator  # noqa: F401
    from pydantic import EmailStr
except ImportError:
    EmailStr = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]

from lila.core.request import Request
from lila.core.responses import JSONResponse, HTMLResponse
from lila.core.cache import Cache
from lila.core.csrf import CSRF
from lila.core.security import Security
from lila.core.translate import Translate
from lila.core.session import Session
from lila.core.logger import Logger


def _cast_param(val: Any, target_type: Type) -> Any:
    if val is None:
        return None
    if target_type is int:
        return int(val)
    if target_type is float:
        return float(val)
    if target_type is bool:
        return str(val).strip().lower() in ("true", "1", "yes", "on")
    if target_type is str:
        return str(val)
    return val


class RouteInspector:
    """Pre-analyzes route handlers once during registration for ultra-fast dispatch."""

    def __init__(self, handler: Callable):
        self.handler = handler
        self.is_async = asyncio.iscoroutinefunction(handler)
        self.sig = inspect.signature(handler)

        self.wants_request = False
        self.body_param_name: Optional[str] = None
        self.body_model: Optional[Type[PydanticBaseModel]] = None
        self.path_params: Dict[str, Type] = {}
        self.query_params: Dict[str, tuple[Type, Any]] = {}

        for name, param in self.sig.parameters.items():
            ann = param.annotation
            default = param.default

            if ann is Request or name == "request":
                self.wants_request = True
            elif inspect.isclass(ann) and issubclass(ann, PydanticBaseModel):
                self.body_param_name = name
                self.body_model = ann
            else:
                p_type = ann if ann is not inspect.Parameter.empty else str
                p_default = default if default is not inspect.Parameter.empty else None
                # Mark as query param (path params are matched dynamically at request time)
                self.query_params[name] = (p_type, p_default)


class Router:
    """Ergonomic route collection with FastAPI-style conveniences."""

    def __init__(
        self,
        prefix: str = "",
        tags: Optional[List[str]] = None,
        middlewares: Optional[List[Callable]] = None,
    ):
        self.prefix = prefix.rstrip("/")
        self.tags = tags or []
        self.middlewares = middlewares or []
        self.routes: List[Union[Route, WebSocketRoute]] = []
        self.openapi_routes: List[dict] = []

    def _normalize_path(self, path: str) -> str:
        p = path.strip()
        full = f"{self.prefix}/{p.lstrip('/')}" if self.prefix else p
        return full if full.startswith("/") else f"/{full}"

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
        csrf: bool = False,
        auth: bool = False,
        sanitize_xss: bool = False,
        summary: Optional[str] = None,
    ) -> None:
        norm_path = self._normalize_path(path)
        inspector = RouteInspector(handler)
        active_model = model or inspector.body_model

        # Apply router-level decorator middlewares if provided
        wrapped_handler = handler
        for mw in reversed(self.middlewares):
            if callable(mw):
                wrapped_handler = mw(wrapped_handler)
        is_wrapped_async = asyncio.iscoroutinefunction(wrapped_handler)

        @wraps(handler)
        async def endpoint_wrapper(request: Request):
            # 1. Rate limiting
            if rate_limit:
                max_req, win = (rate_limit, 60) if isinstance(rate_limit, int) else rate_limit
                client_ip = getattr(request.client, "host", "unknown")
                rl_key = f"rl:r:{handler.__name__}:{client_ip}"
                cnt = await Cache.incr_async(rl_key, ttl=win)
                if cnt > max_req:
                    return JSONResponse(
                        {"success": False, "error": "rate_limit_exceeded", "message": "Rate limit exceeded."},
                        status_code=429,
                        headers={"Retry-After": str(win)},
                    )

            # 2. Auth check
            if auth:
                user = await Session.get_async(request)
                if not user:
                    if request.headers.get("accept", "").startswith("application/json") or request.url.path.startswith("/api/"):
                        return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)
                    from starlette.responses import RedirectResponse
                    return RedirectResponse("/login")
                request.state.user = user

            # 3. Response caching check
            cache_key = None
            if cache and request.method == "GET":
                cache_key = f"route:{norm_path}:{request.url.query}"
                cached = await Cache.get_async(cache_key)
                if cached is not None:
                    if isinstance(cached, (dict, list)):
                        return JSONResponse(cached)
                    if isinstance(cached, str):
                        return HTMLResponse(cached)
                    return cached

            # 4. Extract and cast arguments
            kwargs: Dict[str, Any] = {}
            if inspector.wants_request:
                kwargs["request"] = request

            # Path params
            path_params = request.path_params
            for k, val in path_params.items():
                if k in inspector.sig.parameters:
                    target_t = inspector.sig.parameters[k].annotation
                    target_t = target_t if target_t is not inspect.Parameter.empty else str
                    try:
                        kwargs[k] = _cast_param(val, target_t)
                    except Exception:
                        kwargs[k] = val

            # Query params
            query_params = request.query_params
            for qk, (qt, qdef) in inspector.query_params.items():
                if qk in kwargs or qk in path_params:
                    continue
                if qk in query_params and not inspect.isclass(qdef):
                    try:
                        val = _cast_param(query_params[qk], qt)
                        if sanitize_xss and isinstance(val, str):
                            val = Security.sanitize_str(val)
                        kwargs[qk] = val
                    except Exception:
                        kwargs[qk] = query_params[qk]
                elif qdef is not None:
                    kwargs[qk] = qdef

            # 5. Body parsing and Pydantic validation
            if active_model is not None:
                content_type = request.headers.get("content-type", "")
                data = None
                try:
                    if "application/json" in content_type:
                        data = await request.json()
                    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
                        form = await request.form()
                        data = dict(form)
                    else:
                        try:
                            data = await request.json()
                        except Exception:
                            data = dict(request.query_params)

                    if sanitize_xss and data is not None:
                        data = Security.sanitize_data(data)

                    # Store raw dict in state first so CSRF.verify can read _csrf if needed
                    request.state.data = data
                    validated_body = active_model.model_validate(data)
                    request.state.data = validated_body
                    if inspector.body_param_name:
                        kwargs[inspector.body_param_name] = validated_body
                except ValidationError as val_err:
                    translated = Translate.format_errors(val_err, request=request)
                    return JSONResponse.validation_error(val_err, translated_errors=translated)
                except Exception as err:
                    return JSONResponse({"success": False, "message": f"Malformed payload: {str(err)}"}, status_code=400)

            # 6. CSRF verification (after body parsing so body _csrf is accessible if header isn't used)
            if csrf and request.method in ("POST", "PUT", "DELETE", "PATCH"):
                if not CSRF.verify(request):
                    return JSONResponse({"success": False, "message": "Invalid or missing CSRF token"}, status_code=403)

            # 7. Execute Handler
            try:
                if is_wrapped_async:
                    result = await wrapped_handler(**kwargs)
                else:
                    result = wrapped_handler(**kwargs)
            except Exception as e:
                Logger.error(f"Error handling route {norm_path}: {e}", exception=e)
                raise e

            # 7. Automatic Return Value Casting
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

            # Store in cache if requested
            if cache_key and final_res.status_code == 200:
                if isinstance(result, (dict, list, str)):
                    await Cache.set_async(cache_key, result, ttl=cache)

            return final_res

        route_obj = Route(norm_path, endpoint=endpoint_wrapper, methods=methods, name=name)
        self.routes.append(route_obj)

        self.openapi_routes.append({
            "path": norm_path,
            "methods": methods,
            "summary": summary or handler.__name__.replace("_", " ").title(),
            "inspector": inspector,
            "tags": self.tags,
        })

    # Method Decorators
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

    def websocket(self, path: str):
        """Standard Starlette WebSocket route decorator."""
        def decorator(fn: Callable):
            norm_path = self._normalize_path(path)
            self.routes.append(WebSocketRoute(norm_path, endpoint=fn))
            return fn
        return decorator

    ws = websocket

    def ws_hub(self, path: str, hub: Any):
        """Mounts WebSocketHub automatically on this path."""
        norm_path = self._normalize_path(path)

        async def _endpoint(websocket):
            await hub.handle_connection(websocket)

        self.routes.append(WebSocketRoute(norm_path, endpoint=_endpoint))

    def rest_crud_generate(self, model_sql: Any, base_route: Optional[str] = None):
        """Generates clean, full async REST endpoints for an ActiveRecord model."""
        route_name = base_route or model_sql.__tablename__
        route_prefix = f"/{route_name.strip('/')}"

        @self.get(route_prefix)
        async def list_records(request: Request, limit: int = 100, offset: int = 0):
            return await model_sql.get_all_async(limit=limit, offset=offset)

        @self.get(f"{route_prefix}/{{id:int}}")
        async def get_record(request: Request, id: int):
            rec = await model_sql.get_by_id_async(id)
            if not rec:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return rec

        @self.post(route_prefix)
        async def create_record(request: Request):
            data = await request.json()
            created = await model_sql.insert_async(**data)
            return JSONResponse({"success": True, "data": created}, status_code=201)

        @self.put(f"{route_prefix}/{{id:int}}")
        async def update_record(request: Request, id: int):
            data = await request.json()
            ok = await model_sql.update_async(id, **data)
            if not ok:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return {"success": True, "id": id}

        @self.delete(f"{route_prefix}/{{id:int}}")
        async def delete_record(request: Request, id: int):
            ok = await model_sql.delete_async(id)
            if not ok:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return {"success": True, "deleted": True}
