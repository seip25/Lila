from lila.core.routing import Router
from lila.core.responses import JSONResponse, RedirectResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from app.models.user import User
from lila.core.middleware import session_active, csrf
from pydantic import BaseModel, EmailStr, Field
import traceback
from app.config import DEBUG
from app.connections import connection

class LoginModel(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)

router = Router()

@router.get("/login")
@session_active
async def login_page(request: Request):
    return render(request=request, template="auth/login", csrf=True)

@router.post("/login", model=LoginModel)
@csrf
async def login(request: Request):
    from app.models.auth import LoginAttempt
    input = request.state.data

    user = await User.get_by_email_async(input.email)
    if not user or not user.check_password(input.password):
        db = connection.get_session()
        try:
            client_ip = request.client.host if request.client else "unknown"
            await LoginAttempt.record_attempt(db, input.email, client_ip, False)
            if connection.is_async:
                await db.commit()
            else:
                db.commit()
        finally:
            if connection.is_async:
                await db.close()
            else:
                db.close()
        msg = Translate.t(key="Invalid email or password", request=request)
        return JSONResponse({"success": False, "msg": msg})

    if not user.active:
        msg = Translate.t(key="User is inactive", request=request)
        return JSONResponse({"success": False, "msg": msg})

    db = connection.get_session()
    try:
        client_ip = request.client.host if request.client else "unknown"
        await LoginAttempt.record_attempt(db, input.email, client_ip, True)

        response = JSONResponse({"success": True, "msg": Translate.t(key="Login successful", request=request)})
        await Session.set(request, response, data={"user_id": user.id, "email": user.email, "name": user.name}, key="auth")
        if connection.is_async:
            await db.commit()
        else:
            db.commit()
        return response
    except Exception as e:
        if connection.is_async:
            await db.rollback()
        else:
            db.rollback()
        if DEBUG:
            traceback.print_exc()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        if connection.is_async:
            await db.close()
        else:
            db.close()

routes = router.get_routes()
