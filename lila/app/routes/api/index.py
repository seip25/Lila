from lila.core.request import Request
from lila.core.routing import Router

router = Router(prefix="/api")

@router.get("/")
async def api_root(request: Request):
    """
    API Health check endpoint.
    Automatically returns JSONResponse in Lila v2.0.
    """
    return {
        "status": "healthy",
        "framework": "Lila",
        "version": __import__("lila").__version__,
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

routes = router.get_routes()
