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
    password: str = Field(...)
    password_2: str | None = Field(default=None)

class DeleteAccountModel(BaseModel):
    password: str = Field(..., min_length=8, max_length=20)

@router.get("/dashboard")
@login_required
async def dashboard_page(request):
    session_data = await Session.get(request, "auth")
    context = {"user": session_data} 
    return render(request=request, template="authenticated/dashboard", context=context)

@router.get("/profile")
@login_required
async def profile_page(request):
    session_data = await Session.get(request, "auth")
    context = {"user": session_data}  
    return render(request=request, template="authenticated/profile", context=context)


@router.post("/profile", model=UpdateProfileModel)
@login_required
async def update_profile(request: Request):
    input = request.state.data
    
    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id")
    
    db = connection.get_session()
    try:
        user_db = User.get_by_id(db, user_id)
        if not user_db:
            return JSONResponse({"success": False, "msg": Translate.t(key="Error updating profile", request=request)})
        elif not user_db.check_password(input.password):
            return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)})
        else:
            user_db.name = input.name
            user_db.email = input.email
            if input.password_2 and len(input.password_2) >= 8:
                user_db.set_password(input.password_2)
            db.commit()
            
            response = JSONResponse({"success": True, "msg": Translate.t(key="Profile updated successfully", request=request)})
            await Session.set(request, response, data={"user_id": user_db.id, "email": user_db.email, "name": user_db.name}, key="auth")
            return response 
           
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()

@router.post("/delete-account")
@login_required
async def delete_account(request: Request):
    input = request.state.data
    
    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id")
    body =await request.json()
    password = body.get("password")
    
    db = connection.get_session()
    try:
        user_db = User.get_by_id(db, user_id)
        if not user_db:
            return JSONResponse({"success": False, "msg": Translate.t(key="Error deleting account", request=request)})
        elif not user_db.check_password(password):
            return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)})
        else:
            db.delete(user_db)
            db.commit()
            
            response = JSONResponse({"success": True, "msg": Translate.t(key="Account deleted successfully", request=request)})
            await Session.delete(response, key="auth")
            return response 
           
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()

routes = router.get_routes()
