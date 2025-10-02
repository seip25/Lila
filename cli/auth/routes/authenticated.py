from core.routing import Router
from core.responses import JSONResponse,RedirectResponse
from core.request import Request
from core.templates import render
from core.session import Session
from app.models.user import User
from app.connections import connection
from app.helpers.helpers import translate_, responseValidationError
from pydantic import BaseModel, EmailStr, Field,ValidationError 
from app.middlewares.middlewares import login_required
import traceback

router = Router()

class UpdateProfileModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    password_2: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=8, max_length=20)

    def validate_passwords(self, request: Request):
        msg = translate_(key="Passwords not match", request=request)
        if self.password != self.password_2:
            return JSONResponse({"success": False, "msg": msg})
        return None

class DeleteAccountModel(BaseModel):
    password: str = Field(..., min_length=8, max_length=20)

@router.get("/dashboard")
@login_required
async def dashboard_page(request):
    session_data = Session.unsign("auth", request)
    context = {"user": session_data} 
    return render(request=request, template="dashboard/dashboard", context=context)

@router.get("/profile")
@login_required
async def profile_page(request):
    session_data = Session.unsign("auth", request)
    context = {"user": session_data}  
    return render(request=request, template="dashboard/profile", context=context)

@router.get('/logout')
async def logout_page(request):
    response=RedirectResponse('/login')
    Session.deleteSession(response=response,name_cookie='auth')
    return response

@router.post("/profile")
@login_required
async def update_profile(request):  
    try:
        data = await request.json()
        model = UpdateProfileModel(**data)
        validate = model.validate_passwords(request=request)
        if validate:
            return validate
    except ValidationError as e:
        return responseValidationError(e)
    try:
        db = connection.get_session()
        session_data = Session.unsign("auth", request)
        if not session_data:
            return JSONResponse({"success": False, "msg": translate_("Session expired", request)}, status_code=401)
        
        user = db.query(User).filter_by(token=session_data["token"], active=1).first()
        if not user:
            return JSONResponse({"success": False, "msg": translate_("User not found", request)}, status_code=404)

        if not User.validate_password(user.password, model.password):
            return JSONResponse({"success": False, "msg": translate_("Incorrect current password", request)}, status_code=401)

        user.name = model.name
        user.email = model.email
        if model.password: 
            user.password = User.hash_password(model.password)
        db.commit()

        response = JSONResponse({"success": True, "msg": translate_("Profile updated successfully", request)})
        new_session = {"token": user.token, "name": user.name, "email": user.email}
        Session.setSession(new_val=new_session, name_cookie="auth", response=response)
        return response
    except Exception as e:
        print("ERROR UPDATE_PROFILE:", traceback.format_exc())
        db.rollback()
        return JSONResponse({"success": False, "msg": translate_("Error updating profile", request)}, status_code=400)
    finally:
        db.close()

@router.post("/delete-account")
@login_required
async def delete_account(request):
    
    try:
        data = await request.json()
        model = DeleteAccountModel(**data)
    except ValidationError as e:
        return responseValidationError(e)
    try:
        db = connection.get_session()
        session_data = Session.unsign("auth", request)
        if not session_data:
            return JSONResponse({"success": False, "msg": translate_("Session expired", request)}, status_code=401)

        user = db.query(User).filter_by(token=session_data["token"], active=1).first()
        if not user:
            return JSONResponse({"success": False, "msg": translate_("User not found", request)}, status_code=404)

        if not User.validate_password(user.password, model.password):
            return JSONResponse({"success": False, "msg": translate_("Incorrect password", request)}, status_code=401)

        user.active = 0
        db.commit()
        response = JSONResponse({"success": True, "msg": translate_("Account deleted successfully", request)}) 
        response.delete_cookie("auth")
        return response
    except Exception as e:
        print("ERROR DELETE ACCOUNT:", traceback.format_exc())
        db.rollback()
        return JSONResponse({"success": False, "msg": translate_("Error deleting account", request)}, status_code=400)
    finally:
        db.close()

authenticated_routes = router.get_routes()

