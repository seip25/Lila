from lila.core.routing import Router, EmailStr
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.translate import Translate
from lila.core.oauth import OAuth
from lila.core.auth import PasswordHasher
from lila.core.cache import Cache
from lila.core.logger import Logger
from app.models.user import User
from lila.core.middleware import session_active, csrf
from pydantic import BaseModel, Field
from app.connections import connection
import traceback

try:
    from app.config import DEBUG
except ImportError:
    DEBUG = False


class LoginModel(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


router = Router()

# Auto-mount OAuth routes (/auth/{provider} & /auth/{provider}/callback)
OAuth.mount_routes(router, user_model=User, redirect_to="/dashboard", login_url="/login")


@router.get("/login")
@session_active
async def login_page(request: Request):
    return render(request=request, template="auth/login", csrf=True)


@router.post("/login", model=LoginModel)
@csrf
async def login(request: Request):
    from app.models.auth import LoginAttempt

    input_data = request.state.data
    email = str(input_data.email).strip().lower()
    client_ip = getattr(request.client, "host", "unknown")

    # Basic per-IP throttle (works per worker; use Redis for multi-worker).
    count = await Cache.incr_async(f"rl:login:{client_ip}", ttl=60)
    if count > 20:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Too many attempts", request=request)},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    lock_seconds = await LoginAttempt.get_lock_seconds_async(email)
    if lock_seconds > 0:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Account temporarily locked", request=request)},
            status_code=429,
            headers={"Retry-After": str(lock_seconds)},
        )

    user = await User.get_by_email_async(email)
    password_ok = False
    if user is not None and user.password:
        password_ok = await PasswordHasher.verify_async(user.password, input_data.password)

    if not user or not password_ok:
        try:
            async with connection.transaction() as db:
                await LoginAttempt.record_attempt(db, email, client_ip, False)
        except Exception as exc:
            Logger.error(f"Could not record failed login attempt: {exc}", exception=exc)
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Invalid email or password", request=request)},
            status_code=401,
        )

    if not user.active:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="User is inactive", request=request)},
            status_code=403,
        )

    try:
        async with connection.transaction() as db:
            await LoginAttempt.record_attempt(db, email, client_ip, True)

        response = JSONResponse(
            {"success": True, "msg": Translate.t(key="Login successful", request=request)}
        )
        await Session.set_async(
            {"user_id": user.id, "email": user.email, "name": user.name},
            response,
            key="auth",
        )
        return response
    except Exception as exc:
        Logger.error(f"Login error: {exc}", exception=exc)
        return JSONResponse({"success": False, "msg": "Login unavailable"}, status_code=500)


routes = router.get_routes()
