from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.translate import Translate
from lila.core.middleware import csrf
from lila.core.auth import PasswordHasher
from lila.core.logger import Logger
from app.models.user import User
from app.connections import connection

router = Router()


@router.get("/change-password/{token}")
async def change_password_page(request: Request):
    from app.models.auth import PasswordResetToken

    token = request.path_params.get("token")
    try:
        async with connection.transaction() as db:
            is_valid = await PasswordResetToken.validate_token(db, token)
    except Exception as exc:
        Logger.error(f"Change-password token validation error: {exc}", exception=exc)
        is_valid = None

    if not is_valid:
        return render(request=request, template="auth/invalid-token", status_code=400)
    return render(
        request=request, template="auth/change-password", context={"token": token}, csrf=True
    )


@router.post("/change-password")
@csrf
async def change_password(request: Request):
    from app.models.auth import PasswordResetToken

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "msg": "Invalid request"}, status_code=400)

    token = str((body or {}).get("token") or "")
    password = str((body or {}).get("new_password") or "")
    password_2 = str((body or {}).get("confirm_password") or "")

    if not password or password != password_2:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Passwords not match", request=request)},
            status_code=422,
        )
    if len(password) < 8:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Password must be at least 8 characters", request=request)},
            status_code=422,
        )

    try:
        async with connection.transaction() as db:
            user_id = await PasswordResetToken.validate_token(db, token)
            if not user_id:
                return JSONResponse(
                    {"success": False, "msg": Translate.t(key="Invalid or expired token", request=request)},
                    status_code=400,
                )
            user = await db.get(User, user_id)
            if not user or not user.active:
                return JSONResponse(
                    {"success": False, "msg": Translate.t(key="Invalid or expired token", request=request)},
                    status_code=400,
                )
            user.password = await PasswordHasher.hash_async(password)
            from sqlalchemy import select

            result = await db.execute(
                select(PasswordResetToken).where(PasswordResetToken.token == PasswordResetToken._hash(token))
            )
            token_row = result.scalars().first()
            if token_row:
                await db.delete(token_row)
    except Exception as exc:
        Logger.error(f"Change-password error: {exc}", exception=exc)
        return JSONResponse({"success": False, "msg": "Password change unavailable"}, status_code=500)

    return JSONResponse(
        {"success": True, "msg": Translate.t(key="Password changed successfully", request=request)}
    )


routes = router.get_routes()
