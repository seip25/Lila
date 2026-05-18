from core.request import Request 
from core.routing import Router 
from core.templates import render,renderMarkdown
from core.session import Session
from core.responses import RedirectResponse,PlainTextResponse
from app.config import LANG_DEFAULT,HOST,PORT  

# English: Creating an instance of Router to define routes
# Español: Creando una instancia del Router para definir las rutas
router = Router()
 
# English: Example render html file with Jinja2, passing translation parameters in the context
# Español : Ejemplo renderizar archivo html con Jinja2, pasandole parametros de traduccion en el contexto
@router.get("/")
async def home(request: Request):
    context ={
        "url": f"http://{HOST}:{PORT}"
    }
    response = render(
        request=request, template="index",context=context
    )  # English: Renders the 'index' template with  translations | Español: Renderiza la plantilla 'index' con traducciones
    return response

# English: Example default lang in the path
# Español : Ejemplo de dejar el idioma por defecto en la ruta
@router.get("/es")
async def home(request: Request):
    response = render(
        request=request, template="index",lang_default="es"
    )  
    return response

# English: Example default lang in the path
# Español : Ejemplo de dejar el idioma por defecto en la ruta
@router.get("/en")
async def home(request: Request):
    response = render(
        request=request, template="index",lang_default="en"
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
    # English: Gets the language from the path parameters, falling back to the default if not found
    # Español: Obtiene el idioma de los parámetros de la ruta, usando el valor por defecto si no se encuentra
    lang = request.path_params.get("lang", LANG_DEFAULT)
    if not lang:
        lang = request.query_params.get("lang", LANG_DEFAULT)
    referer = request.headers.get("Referer", "/")
    response = RedirectResponse(url=referer)
    Session.setSession(name_cookie="lang", new_val=lang, response=response)
    return response


@router.get("/changelogs")
async def changelogs(request: Request):
    response =renderMarkdown(request=request, file="changelogs",translate_files=["changelogs"])
    return response

routes = router.get_routes()
