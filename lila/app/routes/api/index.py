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
        "version": "2.0.1",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

routes = router.get_routes()
