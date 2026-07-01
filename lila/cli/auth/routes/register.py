from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from app.models.user import User
from lila.core.middleware import session_active
from pydantic import BaseModel, EmailStr, Field
import traceback
from app.config import DEBUG
from app.connections import connection

class RegisterModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    password_2: str = Field(..., min_length=8, max_length=20)

    def validate_passwords(self, request: Request):
        msg = Translate.t(key="Passwords not match", request=request)
        if self.password != self.password_2:
            return JSONResponse({"success": False, "msg": msg})

router = Router()

@router.get("/register")
@session_active
async def register_page(request: Request):
    return render(request=request, template="auth/register")

@router.post("/register", model=RegisterModel)
async def register(request: Request):
    input = request.state.data
    valid_pass = input.validate_passwords(request)
    if valid_pass:
        return valid_pass

    if await User.get_by_email_async(input.email):
        msg = Translate.t(key="User already exists", request=request)
        return JSONResponse({"success": False, "msg": msg})
    if await User.get_by_email_async(input.email, 0):
        msg = Translate.t(key="User is inactive", request=request)
        return JSONResponse({"success": False, "msg": msg})

    db = connection.get_session()
    try:
        user = User(email=input.email, name=input.name)
        user.set_password(input.password)
        db.add(user)
        db.commit()
        msg = Translate.t(key="User registered successfully", request=request)
        response = JSONResponse({"success": True, "msg": msg})
        await Session.set(request=request, response=response, data={"user_id": user.id, "email": user.email, "name": user.name}, key="auth")
        return response
    except Exception as e:
        db.rollback()
        if DEBUG:
            traceback.print_exc()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()

routes = router.get_routes()
