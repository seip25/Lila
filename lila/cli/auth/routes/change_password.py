from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.translate import Translate
from lila.core.middleware import csrf
from app.models.user import User
from app.connections import connection

router = Router()

@router.get("/change-password/{token}")
async def change_password_page(request: Request):
    from app.models.auth import PasswordResetToken
    token = request.path_params.get("token")
    db = connection.get_session()
    try:
        if not PasswordResetToken.validate_token(db, token):
            return render(request=request, template="auth/invalid-token")
        return render(request=request, template="auth/change-password", context={"token": token}, csrf=True)
    finally:
        db.close()

@router.post("/change-password")
@csrf
async def change_password(request: Request):
    from app.models.auth import PasswordResetToken
    body = await request.json()
    token = body.get("token")
    try:
        password = body.get("new_password")
        password_2 = body.get("confirm_password")

        if not password or password != password_2:
            return JSONResponse({"success": False, "msg": Translate.t(key="Passwords not match", request=request)})

        db = connection.get_session()
        user_id = PasswordResetToken.validate_token(db, token)
        if not user_id:
            return JSONResponse({"success": False, "msg": Translate.t(key="Invalid or expired token", request=request)})

        user = db.query(User).get(user_id)
        user.set_password(password)
        db.query(PasswordResetToken).filter_by(token=token).delete()
        db.commit()

        return JSONResponse({"success": True, "msg": Translate.t(key="Password changed successfully", request=request)})
    except Exception as e:
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        if 'db' in locals():
            db.close()

routes = router.get_routes()
