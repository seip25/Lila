import os
from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.translate import Translate
from lila.core.middleware import session_active, csrf
from lila.core.cache import Cache
from lila.core.config import ENV_CONFIG, is_debug
from lila.core.mailer import Mailer
from lila.core.logger import Logger
from app.models.user import User
from app.connections import connection

router = Router()


@router.get("/forgot-password")
@session_active
async def forgot_password_page(request: Request):
    return render(request=request, template="auth/forgot-password", csrf=True)


@router.post("/forgot-password")
@csrf
async def forgot_password(request: Request):
    client_ip = getattr(request.client, "host", "unknown")
    count = await Cache.incr_async(f"rl:forgot:{client_ip}", ttl=300)
    if count > 5:
        return JSONResponse(
            {"success": False, "msg": Translate.t(key="Too many attempts", request=request)},
            status_code=429,
            headers={"Retry-After": "300"},
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"success": False, "msg": "Invalid request"}, status_code=400)
    email = str((body or {}).get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"success": False, "msg": "Email is required"}, status_code=400)

    token = None
    try:
        user = await User.get_by_email_async(email)
        if user:
            from app.models.auth import PasswordResetToken

            async with connection.transaction() as db:
                token = PasswordResetToken.create_token(db, user.id)
    except Exception as exc:
        Logger.error(f"Forgot-password token error: {exc}", exception=exc)

    if token:
        base_url = str(ENV_CONFIG.get("APP_URL", "") or "").rstrip("/")
        if not base_url:
            base_url = str(request.base_url).rstrip("/")
        reset_url = f"{base_url}/change-password/{token}"
        sent = False
        try:
            smtp_configured = bool(
                os.environ.get("SMTP_HOST") or os.environ.get("SMTP_USER") or os.environ.get("SMTP_FROM")
            )
            if smtp_configured:
                subject = "Reset your Lila password"
                html_body = (
                    '<p>Hi,</p>'
                    f'<p>We received a request to reset your password. This link expires in 30 minutes:</p>'
                    f'<p><a href="{reset_url}">{reset_url}</a></p>'
                    "<p>If you did not request this, you can ignore this email.</p>"
                )
                sent = await Mailer.send_email(email, subject, html_body)
        except Exception as exc:
            Logger.error(f"Forgot-password email error: {exc}", exception=exc)

        if not sent and is_debug():
            print(f"[Lila Auth] Password reset URL for {email}: {reset_url}")

    # Always the same response to avoid account enumeration.
    return JSONResponse(
        {"success": True, "msg": Translate.t(key="If the email exists, a reset link has been sent", request=request)}
    )


routes = router.get_routes()
