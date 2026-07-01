from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.translate import Translate
from lila.core.middleware import session_active
from app.models.user import User
from app.connections import connection
from app.config import DEBUG, HOST, PORT

router = Router()

@router.get("/forgot-password")
@session_active
async def forgot_password_page(request: Request):
    return render(request=request, template="auth/forgot-password")

@router.post("/forgot-password")
async def forgot_password(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        if not email:
            return JSONResponse({"success": False, "msg": "Email is required"}, status_code=400)

        user = await User.get_by_email_async(email)
        if user:
            from app.models.auth import PasswordResetToken
            db = connection.get_session()
            try:
                token = PasswordResetToken.create_token(db, user.id)
                db.commit()
                if DEBUG:
                    url = f"http://{HOST}:{PORT}/change-password/{token}"
                    print(f"DEBUG {url}")
            finally:
                db.close()

        msg = Translate.t(key="If the email exists, a reset link has been sent", request=request)
        return JSONResponse({"success": True, "msg": msg})
    except Exception as e:
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        if 'db' in locals():
            db.close()

routes = router.get_routes()
