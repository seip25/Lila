from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from lila.core.middleware import login_required
from app.models.user import User
from app.connections import connection
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
    return render(request=request, template="authenticated/profile", context=context)


@router.post("/profile", model=UpdateProfileModel)
async def update_profile(request: Request):
    input = request.state.data

    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id")

    # Non-blocking async fetch
    user_db = await User.get_by_id_async(user_id)
    if not user_db:
        return JSONResponse({"success": False, "msg": Translate.t(key="Error updating profile", request=request)})

    # Perform slow Argon2 verification outside of database session
    if not user_db.check_password(input.password):
        return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)})

    db = connection.get_session()
    try:
        # Fetch the model within the session transaction to perform the write
        user_to_update = User.get_by_id(db, user_id)
        user_to_update.name = input.name
        if input.password_2 and len(input.password_2) >= 8:
            user_to_update.set_password(input.password_2)
        db.commit()

        response = JSONResponse({"success": True, "msg": Translate.t(key="Profile updated successfully", request=request)})
        await Session.set(request, response, data={"user_id": user_to_update.id, "email": user_to_update.email, "name": user_to_update.name}, key="auth")
        return response
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()


@router.post("/delete-account", model=DeleteAccountModel)
async def delete_account(request: Request):
    input = request.state.data

    session_data = await Session.get(request, "auth")
    user_id = session_data.get("user_id")
    password = input.password

    # Non-blocking async fetch
    user_db = await User.get_by_id_async(user_id)
    if not user_db:
        return JSONResponse({"success": False, "msg": Translate.t(key="Error deleting account", request=request)})

    # Perform slow Argon2 verification outside of database session
    if not user_db.check_password(password):
        return JSONResponse({"success": False, "msg": Translate.t(key="Incorrect password", request=request)})

    db = connection.get_session()
    try:
        User.delete(db, user_id)

        response = JSONResponse({"success": True, "msg": Translate.t(key="Account deleted successfully", request=request)})
        await Session.delete(response, key="auth")
        return response
    except Exception as e:
        db.rollback()
        return JSONResponse({"success": False, "msg": str(e)}, status_code=500)
    finally:
        db.close()


routes = router.get_routes()
