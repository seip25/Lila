from core.routing import Router
from core.responses import JSONResponse,RedirectResponse
from core.request import Request
from core.templates import render
from core.session import Session
from core.translate import Translate
from app.models.user import User
from app.connections import connection
from pydantic import BaseModel, EmailStr, Field, ValidationError 
from core.middleware import login_required
import traceback

router = Router()

class UpdateProfileModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    password_2: str = Field(..., min_length=8, max_length=20)

    def validate_passwords(self, request: Request):
        msg = Translate.t(key="Passwords not match", request=request)
        if self.password != self.password_2:
            return JSONResponse({"success": False, "msg": msg})
        return None

class DeleteAccountModel(BaseModel):
    password: str = Field(..., min_length=8, max_length=20)

@router.get("/dashboard")
@login_required
async def dashboard_page(request):
    session_data = Session.getSessionValue(request, "auth")
    context = {"user": session_data} 
    return render(request=request, template="authenticated/dashboard", context=context)

@router.get("/profile")
@login_required
async def profile_page(request):
    session_data = Session.getSessionValue(request, "auth")
    context = {"user": session_data}  
    return render(request=request, template="authenticated/profile", context=context)


@router.post("/profile", model=UpdateProfileModel)
@login_required
async def update_profile(request: Request):
    input = request.state.data
    
    session_data = Session.getSessionValue(request, "auth")
    user_id = session_data.get("user_id")
    
    db = connection.get_session()
    try:
        user_db =User.get_by_id(db,user_id)
        if not user_db or not user_db.check_password(input.password):
            response = JSONResponse({"success": False, "msg": Translate.t(key="Error updating profile", request=request)})
        else:
            user = db.query(User).get(user_id)
            user.name = input.name
            user.email = input.email
            if input.password:
                user.set_password(input.password_2)
            db.commit()
            
            response = JSONResponse({"success": True, "msg": Translate.t(key="Profile updated successfully", request=request)})
            Session.setSession({"user_id": user.id, "email": user.email}, response, name_cookie="auth")
            return response 
           
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()

routes = router.get_routes()
