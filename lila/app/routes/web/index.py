from lila.core.request import Request
from lila.core.routing import Router
from lila.core.templates import render
from app.config import APP_URL, HOST, PORT

router = Router()

@router.get("/")
async def home(request: Request):
    """
    Renders the default landing page.
    """
    context = {
        "url": APP_URL if APP_URL else f"http://{HOST}:{PORT}",
        "title": "Lila Framework v2.0.0",
    }
    return render(request=request, template="index", context=context)

routes = router.get_routes()
