from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from lila.core.auth import PasswordHasher
from lila.core.middleware import login_required, csrf
from app.models.user import User
from pydantic import BaseModel, Field

router = Router(middlewares=[login_required])


class UpdateProfileModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=20)
    password_2: str | None = Field(default=None, min_length=8, max_length=20)


class DeleteAccountModel(BaseModel):
    password: str = Field(..., min_length=8, max_length=20)


@router.get("/profile")
async def profile_page(request: Request):
    session_data = await Session.get(request, "auth")
    context = {"user": session_data}
    return render(request=request, template="authenticated/profile", context=context, csrf=True)


@router.post("/profile", model=UpdateProfileModel)
@csrf
async def update_profile(request: Request):
    input = request.state.data

    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id") if session_data else None

    user_db = await User.get_by_id_async(user_id)
    if not user_db:
        return JSONResponse({"success": False, "msg": Translate.t(key="Error updating profile", request=request)})
    if not PasswordHasher.verify(user_db.get("password", ""), input.password):
        return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)})

    try:
        update_fields = {"name": input.name}
        if input.password_2 and len(input.password_2) >= 8:
            update_fields["password"] = PasswordHasher.hash(input.password_2)

        await User.update_async(user_id, **update_fields)

        response = JSONResponse({"success": True, "msg": Translate.t(key="Profile updated successfully", request=request)})
        await Session.set(
            request,
            response,
            data={"user_id": user_db["id"], "email": user_db["email"], "name": input.name},
            key="auth",
        )
        return response
    except Exception as e:
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)


@router.post("/delete-account", model=DeleteAccountModel)
@csrf
async def delete_account(request: Request):
    input = request.state.data

    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id") if session_data else None
    password = input.password

    user_db = await User.get_by_id_async(user_id)
    if not user_db:
        return JSONResponse({"success": False, "msg": Translate.t(key="Error deleting account", request=request)})
    if not PasswordHasher.verify(user_db.get("password", ""), password):
        return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)})

    try:
        await User.delete_async(user_id)
        response = JSONResponse({"success": True, "msg": Translate.t(key="Account deleted successfully", request=request)})
        await Session.delete(response, key="auth", request=request)
        return response
    except Exception as e:
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)


routes = router.get_routes()
