from lila.core.routing import Router
from lila.core.admin import admin_routes

router = Router()

def Admin(models: list,default_route: str = "admin") -> Router:
    """
    Function to register admin routes for the given models.
    Returns the router with all registered routes.
    """ 
    generated_routes = admin_routes(models=models, router=router,default_route=default_route)
    return generated_routes.get_routes()


routes = router.get_routes() 