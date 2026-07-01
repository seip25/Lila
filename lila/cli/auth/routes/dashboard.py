from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request
from lila.core.templates import render
from lila.core.session import Session
from lila.core.middleware import login_required

router = Router(middlewares=[login_required])

@router.get("/dashboard")
async def dashboard_page(request: Request):
    session_data = await Session.get(request, "auth")
    context = {"user": session_data}
    return render(request=request, template="authenticated/dashboard", context=context)

routes = router.get_routes()
