from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from lila.core.auth import PasswordHasher
from lila.core.middleware import login_required, csrf
from lila.core.logger import Logger
from app.models.user import User
from pydantic import BaseModel, Field

router = Router(middlewares=[login_required])


class UpdateProfileModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)  # current password
    password_2: str | None = Field(default=None, min_length=8, max_length=128)


class DeleteAccountModel(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


@router.get("/profile")
async def profile_page(request: Request):
    session_data = await Session.get(request, "auth")
    context = {"user": session_data}
    return render(request=request, template="authenticated/profile", context=context, csrf=True)


@router.post("/profile", model=UpdateProfileModel)
@csrf
async def update_profile(request: Request):
    input_data = request.state.data
    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id") if isinstance(session_data, dict) else None
    if not user_id:
        return JSONResponse({"success": False, "msg": Translate.t(key="Authentication required", request=request)}, status_code=401)

    user = await User.get_by_id_with_password_async(user_id)
    if not user:
        return JSONResponse({"success": False, "msg": Translate.t(key="Error updating profile", request=request)}, status_code=404)

    if not await PasswordHasher.verify_async(user.password or "", input_data.password):
        return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)}, status_code=403)

    try:
        name = input_data.name.strip()
        if input_data.password_2:
            new_hash = await PasswordHasher.hash_async(input_data.password_2)
            await User.update_async(user_id, name=name, password=new_hash)
        else:
            await User.update_async(user_id, name=name)

        response = JSONResponse(
            {"success": True, "msg": Translate.t(key="Profile updated successfully", request=request)}
        )
        await Session.set_async(
            {"user_id": user.id, "email": user.email, "name": name},
            response,
            key="auth",
        )
        return response
    except Exception as exc:
        Logger.error(f"Profile update error: {exc}", exception=exc)
        return JSONResponse({"success": False, "msg": "Profile update unavailable"}, status_code=500)


@router.post("/delete-account", model=DeleteAccountModel)
@csrf
async def delete_account(request: Request):
    input_data = request.state.data
    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id") if isinstance(session_data, dict) else None
    if not user_id:
        return JSONResponse({"success": False, "msg": Translate.t(key="Authentication required", request=request)}, status_code=401)

    user = await User.get_by_id_with_password_async(user_id)
    if not user:
        return JSONResponse({"success": False, "msg": Translate.t(key="Error deleting account", request=request)}, status_code=404)

    if not await PasswordHasher.verify_async(user.password or "", input_data.password):
        return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)}, status_code=403)

    try:
        await User.delete_async(user_id)
        response = JSONResponse(
            {"success": True, "msg": Translate.t(key="Account deleted successfully", request=request)}
        )
        await Session.delete_async(request, response, key="auth")
        return response
    except Exception as exc:
        Logger.error(f"Delete-account error: {exc}", exception=exc)
        return JSONResponse({"success": False, "msg": "Account deletion unavailable"}, status_code=500)


routes = router.get_routes()
