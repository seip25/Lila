from core.routing import Router
from core.responses import JSONResponse,RedirectResponse
from core.request import Request
from core.templates import render
from core.session import Session
from core.translate import Translate
from core.auth import generate_token_value
from app.models.user import User
from app.models.auth import LoginAttempt,LoginAttemptHistory,LoginSuccessHistory,PasswordResetToken
from app.connections import connection
from pydantic import BaseModel, EmailStr, Field, ValidationError
import datetime
from core.middleware import session_active 
import traceback
from app.config import DEBUG,HOST,PORT

class RegisterModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    password_2: str = Field(..., min_length=8, max_length=20)
    def validate_passwords(self, request: Request):
        msg = Translate.t(key="Passwords not match", request=request)
        if self.password != self.password_2:
            response = JSONResponse({"success": False, "msg": msg})
            return response

class LoginModel(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)

router = Router()

@router.get("/login")
@session_active
async def login_page(request):
    return render(request=request, template="auth/login")

@router.get("/register")
@session_active
async def register_page(request):
    return render(request=request, template="auth/register")

    
@router.get("/forgot-password")
@session_active
async def forgot_password_page(request):
    return render(request=request, template="auth/forgot-password")

@router.post("/register", model=RegisterModel)
async def register(request: Request):
    input = request.state.data
    valid_pass = input.validate_passwords(request)
    if valid_pass:
        return valid_pass
    
    db = connection.get_session()
    try:
        if User.get_by_email(db, input.email):
            msg = Translate.t(key="User already exists", request=request)
            return JSONResponse({"success": False, "msg": msg})
        
        user = User(email=input.email, name=input.name)
        user.set_password(input.password)
        db.add(user)
        db.commit()
        msg = Translate.t(key="User registered successfully", request=request)
        return JSONResponse({"success": True, "msg": msg})
    except Exception as e:
        db.rollback()
        if DEBUG:
            traceback.print_exc()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()

@router.post("/login", model=LoginModel)
async def login(request: Request):
    input = request.state.data
    db = connection.get_session()
    try:
        user = User.get_by_email(db, input.email)
        if not user or not user.check_password(input.password):
            LoginAttempt.record_attempt(db, input.email, request.client.host, False)
            db.commit()
            msg = Translate.t(key="Invalid email or password", request=request)
            return JSONResponse({"success": False, "msg": msg})
        
        if not user.active:
            msg = Translate.t(key="User is inactive", request=request)
            return JSONResponse({"success": False, "msg": msg})

        LoginAttempt.record_attempt(db, input.email, request.client.host, True)
        
        response = JSONResponse({"success": True, "msg": Translate.t(key="Login successful", request=request)})
        await Session.set(request, response, data={"user_id": user.id, "email": user.email, "name": user.name}, key="auth")
        db.commit()
        return response
    except Exception as e:
        if DEBUG:
            traceback.print_exc()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()

@router.post("/logout")
async def logout(request: Request):
    response = JSONResponse({"success": True, "msg": Translate.t(key="Logged out successfully", request=request)})
    await Session.delete(response, key="auth")
    return response

@router.get("/logout")
async def logout_get(request: Request):
    response = RedirectResponse("/login")
    await Session.delete(response, key="auth")
    return response

@router.post("/forgot-password")
async def forgot_password(request: Request):
    try:
        body = await request.json()
        email = body.get("email")
        if not email:
             return JSONResponse({"success": False, "msg": "Email is required"}, status_code=400)
        
        db = connection.get_session()
        user = User.get_by_email(db, email)
        if user:
            token = PasswordResetToken.create_token(db, user.id)
            db.commit() 
            if DEBUG:
                url = f"http://{HOST}:{PORT}/change-password/{token}"
                print(f"DEBUG {url}")
        
        msg = Translate.t(key="If the email exists, a reset link has been sent", request=request)
        return JSONResponse({"success": True, "msg": msg})
    except Exception as e:
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        if 'db' in locals(): db.close()

@router.get("/change-password/{token}")
async def change_password_page(request: Request):
    token = request.path_params.get("token")
    db = connection.get_session()
    try:
        if not PasswordResetToken.validate_token(db, token):
            return render(request=request, template="auth/invalid-token")
        return render(request=request, template="auth/change-password", context={"token": token})
    finally:
        db.close()

@router.post("/change-password")
async def change_password(request: Request):
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
        if 'db' in locals(): db.close()

routes = router.get_routes()
