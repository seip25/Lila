from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.routing import Router
from app.config import DEBUG

# English: Initialize the router instance for managing API routes.
# Español: Inicializa la instancia del enrutador para manejar rutas de la API.
router = Router(prefix="api/v1")


# English: Define a simple API health-check route.
# Español: Define una ruta simple de verificación del API.
@router.get("/")
async def api(request: Request):
    """Api root — use /docs for Swagger UI and /openapi.json for schema"""
    return JSONResponse({"api": True})


# English: Enable Swagger UI for API documentation.
# Español: Habilita Swagger UI para la documentación de la API.
router.swagger_ui()

# English: Generate OpenAPI JSON for external tools.
# Español: Genera JSON de OpenAPI para herramientas externas.
router.openapi_json()

# English: Retrieve all defined routes in the application.
# Español: Obtiene todas las rutas definidas en la aplicación.
routes = router.get_routes()
