from core.request import Request 
from core.routing import Router, locales 
from core.templates import render,renderMarkdown
from core.responses import RedirectResponse
from core.translate import Translate
from app.config import LANG_DEFAULT,HOST,PORT  

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
    context ={
        "url": f"http://{HOST}:{PORT}"
    }
    response = render(
        request=request, template="index",context=context
    )
    return response

# English : Example for render 'markdown' file
# Español : Ejemplo para renderizar un archivo 'markdown'
@router.get("/markdown")
async def home(request: Request):
    # English: Define a list of CSS files to include in the response
    # Español: Define una lista de archivos CSS para incluir en la respuesta
    css = ["/public/css/styles.css"]
    # English: Renders a markdown file with materialcss styling
    # Español: Renderiza un archivo markdown con el estilo materialcss
    response = renderMarkdown(
        request=request, file="example", css_files=css
    )
    return response


# English: Example route for changing the language
# Español: Ejemplo de ruta para cambiar el idioma
@router.get("/set-language/{lang}")
async def set_language(request: Request):
    lang = request.path_params.get("lang", LANG_DEFAULT)
    referer = request.headers.get("Referer", "/")
    response = RedirectResponse(url=referer)
    await Translate.set_lang(request, response, lang)
    return response


@router.get("/changelogs")
async def changelogs(request: Request):
    response =renderMarkdown(request=request, file="changelogs",translate_files=["changelogs"])
    return response

routes = router.get_routes()
