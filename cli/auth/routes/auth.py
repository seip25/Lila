from core.routing import Router
from core.responses import JSONResponse
from core.request import Request
from core.templates import render
from core.session import Session
from app.models.user import User
from app.models.auth import LoginAttempt,LoginAttemptHistory,LoginSuccessHistory,PasswordResetToken
from app.connections import connection
from app.helpers.helpers import translate_,responseValidationError,generate_token_value
from pydantic import BaseModel, EmailStr,  Field,ValidationError
import datetime
from app.middlewares.middlewares import session_active 
import traceback
from app.config import DEBUG,HOST,PORT

class RegisterModel(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str= Field(...,min_length=8, max_length=20)
    password_2: str =Field(...,min_length=8, max_length=20)
    def validate_passwords(self, request: Request):
        msg = translate_(key="Passwords not match", request=request)
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

@router.get('/change-password')
@session_active
async def change_password_page(request):
    email = request.query_params.get('email')
    token = request.query_params.get('token')
    db = connection.get_session()
    try:
        if not email or not token or not PasswordResetToken.validate_token(db, email, token):
            return render(request=request, template="auth/invalid-token")
        return render(request=request, template="auth/change-password", context={"email": email, "token": token})
    finally:
        db.close()


@router.post("/login")
async def login(request):
    try:
        data = await request.json()
        login_data = LoginModel(**data)
    except ValidationError as e:
         return JSONResponse({"success": False, "msg": translate_("Incorrect email or password", request)}, status_code=401)

    db = connection.get_session()
    try:
        login_attempt = db.query(LoginAttempt).filter_by(email=login_data.email).first()
        if login_attempt and login_attempt.is_locked():
            login_attempt.attempts = 0
            db.commit() 
            return JSONResponse({"msg": translate_("Account locked. Try again in 5 minutes.", request)}, status_code=429)

        ip = request.client.host
        device = request.headers.get("User-Agent", "Unknown")

        user = User.check_login(db, email=login_data.email)
        if user and User.validate_password(user.password, login_data.password):
            if login_attempt:
                login_attempt.attempts = 0
                login_attempt.locked_at = None
                db.commit()
                  
            
            details = f"Successful login for {login_data.email}"
            login_success = LoginSuccessHistory(email=login_data.email, ip_address=ip, device=device, details=details)
            db.add(login_success)
            db.commit() 
            response = JSONResponse({"success": True, "msg": translate_("Login successful", request)})
            user_session = {"token": user.token,"email":user.email,"name": user.name }
            Session.setSession(new_val=user_session, name_cookie="auth", response=response)
            return response
        else:
            login_history = LoginAttemptHistory(email=login_data.email, ip_address=ip, device=device, details="Failed login attempt")
            db.add(login_history)
            db.commit() 

            if not login_attempt:
                login_attempt = LoginAttempt(email=login_data.email)
                db.add(login_attempt)
                db.flush()
            login_attempt.attempts += 1
            if login_attempt.attempts >= 5:
                login_attempt.locked_at = datetime.datetime.utcnow()
            
            db.commit()
            return JSONResponse({"success": False, "msg": translate_("Incorrect email or password", request)}, status_code=401)
    except Exception as e:
        print("ERROR LOGIN:", traceback.format_exc())
    finally:
        db.close()

@router.post("/register")
async def register(request):
    
    try:
        data = await request.json()
        model = RegisterModel(**data)
        validate = model.validate_passwords(request=request)
        if isinstance(validate, JSONResponse):
            return validate
    except ValidationError as e:
        return responseValidationError(e)

    try:
        db = connection.get_session()    
        if User.check_for_email(db, email=model.email):
            return JSONResponse({"success": False, "msg": translate_("Email already exists", request)}, status_code=400)

        user = User.insert(db, {"name": model.name, "email": model.email, "password": model.password})
        db.commit() 
        if user:
            response=JSONResponse({"success": True, "msg": translate_("User created successfully", request)})
            user_session = {"token": user.token,"email":user.email,"name": user.name }
            Session.setSession(new_val=user_session, name_cookie="auth", response=response)
            return response
    except Exception as e:
        print("ERROR REGISTER:", traceback.format_exc())
        db.rollback()
        return JSONResponse({"success": False, "msg": translate_("Error creating account, check your entered data", request)}, status_code=400)
    finally:
        db.close()
    
    return JSONResponse({"success": False, "msg": translate_("Error creating account", request)}, status_code=500)

@router.post("/forgot-password")
async def forgot_password(request):
    try:
        data = await request.json() 
    except Exception as e:
        print("ERROR REGISTER:", traceback.format_exc())
    try:
        db = connection.get_session()
        email = data.get("email")
        
        if User.check_for_email(db, email=email):
            
            token =generate_token_value()
            create_token= PasswordResetToken.create_token(db,email,token)
            if create_token:
                if DEBUG:
                    link= f"http://{HOST}:{PORT}/change-password?token={token}&email={email}"  
                    print(f"Password reset link for {email}: {link}")
                return JSONResponse({"msg": translate_("If an account with that email exists, a password reset link has been sent.", request)})
             
        return JSONResponse({"success":False,"msg": translate_("Operation failed.", request)})
    except Exception as e:
        print("ERROR REGISTER:", traceback.format_exc())
        return JSONResponse({"success":False,"msg": translate_("Operation failed.", request)})
        
    finally:
        db.close()


class ChangePasswordModel(BaseModel):
    email: EmailStr
    token: str
    new_password: str = Field(..., min_length=8, max_length=20)
    confirm_password: str = Field(..., min_length=8, max_length=20)

    def validate_passwords(self, request: Request):
        if self.new_password != self.confirm_password:
            return JSONResponse({"success": False, "msg": translate_("Passwords not match", request)})

@router.post("/change-password")
async def change_password(request):
    try:
        data = await request.json()
        model = ChangePasswordModel(**data)
        validate = model.validate_passwords(request=request)
        if validate:
            return validate
    except ValidationError as e:
        return responseValidationError(e)

    db = connection.get_session()
    try:
        if not PasswordResetToken.validate_token(db, model.email, model.token):
            return JSONResponse({"success": False, "msg": translate_("Invalid or expired token", request)}, status_code=400)

        user = db.query(User).filter_by(email=model.email).first()
        if not user:
            return JSONResponse({"success": False, "msg": translate_("User not found", request)}, status_code=404)

        user.password = User.hash_password(model.new_password)
        db.commit()

        db.query(PasswordResetToken).filter_by(email=model.email, token=model.token).delete()
        db.commit()

        return JSONResponse({"success": True, "msg": translate_("Password changed successfully", request)})
    except Exception as e:
        print("ERROR CHANGE_PASSWORD:", traceback.format_exc())
        db.rollback()
        return JSONResponse({"success": False, "msg": translate_("Error updating profile", request)}, status_code=400)
    finally:
        db.close()    

auth_routes = router.get_routes()
