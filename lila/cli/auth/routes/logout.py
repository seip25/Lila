from lila.core.routing import Router
from lila.core.responses import JSONResponse, RedirectResponse
from lila.core.request import Request
from lila.core.session import Session
from lila.core.translate import Translate
from lila.core.middleware import csrf

router = Router()

@router.post("/logout")
@csrf
async def logout(request: Request):
    response = JSONResponse({"success": True, "msg": Translate.t(key="Logged out successfully", request=request)})
    await Session.delete(response, key="auth")
    return response

@router.get("/logout")
async def logout_get(request: Request):
    response = RedirectResponse("/login")
    await Session.delete(response, key="auth")
    return response

routes = router.get_routes()
