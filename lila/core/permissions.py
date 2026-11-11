"""Roles and permissions.

    from lila.core.permissions import define_roles, require_role, require_permission

    define_roles({
        "admin": ["*"],
        "editor": ["posts.*", "comments.moderate"],
        "user": ["posts.read"],
    })

    @router.get("/admin/stats", roles=["admin"])               # router option
    async def stats(request): ...

    @router.delete("/posts/{id:int}", permissions=["posts.delete"])
    async def delete_post(request, id: int): ...

    @router.get("/reports")
    @require_permission("reports.view")                        # decorator form
    async def reports(request): ...

    {% if can("posts.edit") %}<a href="...">Edit</a>{% endif %}  {# Jinja #}

Roles come from the session user (``"roles": [...]`` or ``"role": "..."``),
from an API key / JWT principal set on ``request.state.user``, or from your
own loader (``set_role_loader(async def loader(request, user) -> list)``),
for example to read them from the database. ``*`` and ``prefix.*`` wildcards
are supported. Not signed in → 401 (API) / redirect to ``/login`` (pages);
signed in without the permission → 403.
"""

from __future__ import annotations

import asyncio
import fnmatch
import inspect
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from lila.core.responses import HTMLResponse, JSONResponse, RedirectResponse

_ROLES: Dict[str, Set[str]] = {}
_ROLE_LOADER: Optional[Callable] = None
LOGIN_URL = "/login"


def define_roles(mapping: Dict[str, Iterable[str]]) -> None:
    """Role → permissions (replaces previous definitions of the same roles)."""
    for role, perms in mapping.items():
        _ROLES[str(role)] = {str(p) for p in perms}


def set_role_loader(loader: Optional[Callable]) -> None:
    """``loader(request, user) -> list[str]`` (sync or async) overrides session roles."""
    global _ROLE_LOADER
    _ROLE_LOADER = loader


def roles_of(user: Any) -> List[str]:
    if not isinstance(user, dict):
        return []
    roles = user.get("roles")
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split(",") if r.strip()]
    result = list(roles or [])
    if user.get("role"):
        result.append(str(user["role"]))
    return result


def permissions_for(roles: Iterable[str], extra: Iterable[str] = ()) -> Set[str]:
    perms: Set[str] = set(extra or ())
    for role in roles:
        perms |= _ROLES.get(role, set())
    return perms


def _match(granted: Set[str], needed: str) -> bool:
    return any(g == "*" or g == needed or fnmatch.fnmatchcase(needed, g) for g in granted)


def has_permission(user: Any, permission: str, roles: Optional[Iterable[str]] = None) -> bool:
    role_list = list(roles) if roles is not None else roles_of(user)
    scopes = user.get("scopes", []) if isinstance(user, dict) else []
    return _match(permissions_for(role_list, scopes), permission)


async def _current_user(request) -> Optional[dict]:
    user = getattr(request.state, "user", None)
    if user:
        return user
    from lila.core.session import Session

    user = await Session.get_async(request)
    if user:
        request.state.user = user
    return user


async def _resolve_roles(request, user) -> List[str]:
    cached = getattr(request.state, "roles", None)
    if cached is not None:
        return cached
    roles = roles_of(user)
    if _ROLE_LOADER is not None:
        loaded = _ROLE_LOADER(request, user)
        if inspect.isawaitable(loaded):
            loaded = await loaded
        roles = list(loaded or [])
    request.state.roles = roles
    return roles


def _wants_json(request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "application/json" in accept or request.url.path.startswith("/api/") or \
        request.headers.get("authorization", "").lower().startswith("bearer ")


async def check_access(request, roles: Iterable[str] = (), permissions: Iterable[str] = ()):
    """Returns ``None`` when allowed, otherwise the 401/303/403 response."""
    roles = list(roles or [])
    permissions = list(permissions or [])
    user = await _current_user(request)
    if not user:
        if _wants_json(request):
            return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)
        return RedirectResponse(LOGIN_URL, status_code=303)
    user_roles = await _resolve_roles(request, user)
    if roles and not set(roles) & set(user_roles):
        return _forbidden(request)
    if permissions:
        granted = permissions_for(user_roles, user.get("scopes", []) if isinstance(user, dict) else [])
        if not all(_match(granted, p) for p in permissions):
            return _forbidden(request)
    return None


def _forbidden(request):
    if _wants_json(request):
        return JSONResponse({"success": False, "message": "Forbidden"}, status_code=403)
    return HTMLResponse("<h1>403 Forbidden</h1>", status_code=403)


def _find_request(args, kwargs):
    from starlette.requests import Request as StarletteRequest

    req = kwargs.get("request")
    if isinstance(req, StarletteRequest):
        return req
    for value in list(args) + list(kwargs.values()):
        if isinstance(value, StarletteRequest):
            return value
    return None


def _guard(roles: Iterable[str] = (), permissions: Iterable[str] = ()):
    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            request = _find_request(args, kwargs)
            if request is None:
                return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)
            denied = await check_access(request, roles, permissions)
            if denied is not None:
                return denied
            result = fn(*args, **kwargs)
            return await result if asyncio.iscoroutine(result) else result

        return wrapper

    return decorator


def require_role(*roles: str):
    """Allows users having **any** of the roles."""
    return _guard(roles=roles)


def require_permission(*permissions: str):
    """Allows users having **all** the permissions (wildcards in role definitions)."""
    return _guard(permissions=permissions)


def jinja_can(request: Any, permission: str) -> bool:
    """Sync check for templates (uses the user already resolved for the request)."""
    if request is None:
        return False
    user = getattr(request.state, "user", None)
    if not user:
        from lila.core.session import Session

        user = Session.get_sync(request)
    if not user:
        return False
    roles = getattr(request.state, "roles", None)
    return has_permission(user, permission, roles)


def jinja_has_role(request: Any, role: str) -> bool:
    if request is None:
        return False
    user = getattr(request.state, "user", None)
    if not user:
        from lila.core.session import Session

        user = Session.get_sync(request)
    roles = getattr(request.state, "roles", None) if request is not None else None
    return role in (roles if roles is not None else roles_of(user))
