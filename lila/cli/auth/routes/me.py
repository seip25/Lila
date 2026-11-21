from lila.core.routing import Router
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.session import Session

router = Router()

# Public fields of the session user sent to the browser (never passwords/tokens).
PUBLIC_USER_FIELDS = ("user_id", "email", "name", "avatar_url")


@router.get("/api/auth/me", openapi=False)
async def me(request: Request):
    """Current user for React (AuthProvider/useAuth): {"user": {...}|null, "roles": [...]}."""
    session_data = await Session.get_async(request, key="auth")
    if not isinstance(session_data, dict) or not session_data.get("user_id"):
        return JSONResponse({"success": True, "user": None, "roles": [], "register_enabled": True},
                            headers={"Cache-Control": "no-store"})
    from lila.core.permissions import resolve_roles

    user = {key: session_data.get(key) for key in PUBLIC_USER_FIELDS if session_data.get(key) is not None}
    user["id"] = session_data.get("user_id")
    roles = await resolve_roles(request, session_data)
    user["roles"] = list(roles)
    return JSONResponse({"success": True, "user": user, "roles": list(roles), "register_enabled": True},
                        headers={"Cache-Control": "no-store"})


routes = router.get_routes()
