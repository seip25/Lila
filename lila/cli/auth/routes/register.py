from lila.core.routing import Router, EmailStr
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from lila.core.auth import PasswordHasher
from lila.core.cache import Cache
from lila.core.logger import Logger
from app.models.user import User
from lila.core.middleware import session_active, csrf
from pydantic import BaseModel, Field
from app.connections import connection


class RegisterModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    password_2: str = Field(..., min_length=8, max_length=128)


router = Router()


@router.get("/register")
@session_active
async def register_page(request: Request):
    return render(request=request, template="auth/register", csrf=True)


@router.post("/register", model=RegisterModel)
@csrf
async def register(request: Request):
    input_data = request.state.data
    email = str(input_data.email).strip().lower()
    client_ip = getattr(request.client, "host", "unknown")

    count = await Cache.incr_async(f"rl:register:{client_ip}", ttl=300)
    if count > 10:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Too many attempts", request=request)},
            status_code=429,
            headers={"Retry-After": "300"},
        )

    if input_data.password != input_data.password_2:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Passwords not match", request=request)},
            status_code=422,
        )

    if await User.get_by_email_async(email):
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="User already exists", request=request)},
            status_code=409,
        )
    if await User.get_by_email_async(email, 0):
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="User is inactive", request=request)},
            status_code=403,
        )

    try:
        async with connection.transaction() as db:
            user = User(email=email, name=input_data.name.strip(), active=1)
            user.password = await PasswordHasher.hash_async(input_data.password)
            db.add(user)
            await db.flush()

        response = JSONResponse(
            {"success": True, "msg": Translate.t(key="User registered successfully", request=request)}
        )
        await Session.set_async(
            {"user_id": user.id, "email": user.email, "name": user.name},
            response,
            key="auth",
        )
        return response
    except Exception as exc:
        Logger.error(f"Registration error: {exc}", exception=exc)
        return JSONResponse(
            {"success": False, "msg": "Registration unavailable"}, status_code=500
        )


routes = router.get_routes()
