from lila.core.request import Request 
from lila.core.routing import Router, locales 
from lila.core.templates import render,renderMarkdown
from lila.core.responses import RedirectResponse
from lila.core.translate import Translate
from app.config import LANG_DEFAULT, HOST, PORT, APP_URL  

# English: Creating an instance of Router to define routes
# Español: Creando una instancia del Router para definir las rutas
router = Router()
 
@router.get("/")
@locales(["es", "en"])
async def home(request: Request):
    """
    English: Example rendering HTML file with Jinja2, using the @locales decorator to automatically register localized prefixes.
    Español: Ejemplo de renderizar un archivo HTML con Jinja2, usando el decorador @locales para registrar prefijos localizados de forma automática.
    """
    # English: APP_URL for production, fallback to HOST:PORT for development.
    # Español: APP_URL para producción, fallback a HOST:PORT para desarrollo.
    context ={
        "url": APP_URL if APP_URL else f"http://{HOST}:{PORT}"
    }
    response = render(
        request=request, template="index",context=context
    )
    return response


routes = router.get_routes()
