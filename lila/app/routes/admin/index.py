from lila.core.routing import Router
from lila.core.admin import admin_routes
from app.models.user import User

router = Router()

def Admin(models: list, default_route: str = "admin", react: bool = False) -> Router:
    """
    Register Admin 2.0 routes for the given models (react=True: React panel).
    """
    return admin_routes(models=models, router=router, default_route=default_route, react=react)

# Auto-register User model in Admin Panel
Admin(models=[User])

routes = router.get_routes()
