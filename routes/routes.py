# Import necessary modules and functions from the core and middlewares
from core.request import Request  # English: Importing Request class to handle HTTP requests | Español: Importando la clase Request para manejar las solicitudes HTTP
from core.routing import Router # English: Importing Router class to define and manage routes | Español: Importando la clase Router para definir y manejar rutas
from core.templates import render,renderMarkdown# English: Importing functions for rendering templates and Markdown files | Español: Importando funciones para renderizar plantillas y archivos Markdown
from core.session import Session # English: Importing Session class for session handling | Español: Importando la clase Session para el manejo de sesiones
from core.responses import RedirectResponse# English: Importing RedirectResponse to handle HTTP redirects | Español: Importando RedirectResponse para manejar redirecciones HTTP
from core.env import LANG_DEFAULT # English: Importing the default language setting from the environment | Español: Importando la configuración de idioma por defecto desde el entorno

# English: Creating an instance of Router to define routes
# Español: Creando una instancia del Router para definir las rutas
router = Router()

# English: Mounting statics files ,in folder 'static',url ='/public'
#  Español: Montando los archivos estaticos en la carpeta 'static',url ='/public'
router.mount()

# English: Example render html file with Jinja2, passing translation parameters in the context
# Español : Ejemplo renderizar archivo html con Jinja2, pasandole parametros de traduccion en el contexto
@router.route(path="/", methods=["GET"])
async def home(request: Request):
    response = render(
        request=request, template="index"
    )  # English: Renders the 'index' template with  translations | Español: Renderiza la plantilla 'index' con traducciones
    return response


# English : Example for render 'markdown' file
# Español : Ejemplo para renderizar un archivo 'markdown'
@router.route(path="/markdown", methods=["GET"])
async def home(request: Request):
    # English: Define a list of CSS files to include in the response
    # Español: Define una lista de archivos CSS para incluir en la respuesta
    css = ["/public/css/styles.css"]
    # English: Renders a markdown file with materialcss styling
    # Español: Renderiza un archivo markdown con el estilo materialcss
    response = renderMarkdown(
        request=request, file="example", css_files=css, materialcss=True
    )
    return response


# English: Example route for changing the language
# Español: Ejemplo de ruta para cambiar el idioma
@router.route(path="/set-language/{lang}", methods=["GET"])
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


# English: Example route for testing reactive features in HTML
# Español: Ejemplo de ruta para probar características reactivas en HTML
@router.route(path="/reactive", methods=["GET"])
async def test(request: Request):
    response= render(request=request, template="reactive/reactive")
    return response

#Englihs : Example route for testing reactive features in HTML with a different template (Login,Register)
#Español: Ejemplo de ruta para probar características reactivas en HTML con una plantilla diferente (Login,Register)
@router.route(path="/auth", methods=["GET"])
async def auth(request: Request):
    response= render(request=request, template="auth/auth")
    return response

# English: Get all the defined routes
#  Español: Obtiene todas las rutas definidas
routes = router.get_routes()
