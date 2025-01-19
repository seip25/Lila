# Import necessary modules and functions from the core and middlewares
from core.request import Request  # English: Importing Request class to handle HTTP requests | Español: Importando la clase Request para manejar las solicitudes HTTP
from core.routing import Router  # English: Importing Router class to define and manage routes | Español: Importando la clase Router para definir y manejar rutas
from core.templates import render, renderMarkdown  # English: Importing functions for rendering templates and Markdown files | Español: Importando funciones para renderizar plantillas y archivos Markdown
from core.session import Session  # English: Importing Session class for session handling | Español: Importando la clase Session para el manejo de sesiones
from core.responses import RedirectResponse  # English: Importing RedirectResponse to handle HTTP redirects | Español: Importando RedirectResponse para manejar redirecciones HTTP
from middlewares.middlewares import login_required, session_active  # English: Importing middlewares for session management and login checks | Español: Importando middlewares para el manejo de sesiones y verificación de login
from core.env import LANG_DEFAULT  # English: Importing the default language setting from the environment | Español: Importando la configuración de idioma por defecto desde el entorno

# Create an instance of the Router to define the routes
router = Router()  # English: Creating an instance of Router to define routes | Español: Creando una instancia del Router para definir las rutas

# Mount the router (the actual implementation is hidden in the router class)
router.mount()  # English: Mounting statics files ,in folder 'static',url ='/public' | Español: Montando los archivos estaticos en la carpeta 'static',url ='/public' 

# Define the home route, which renders the 'index' template for guests
@router.route(path='/', methods=['GET'])  # English: Handles GET requests to the home page | Español: Maneja las solicitudes GET para la página principal
async def home(request: Request):  # English: Handles GET requests to the home page | Español: Maneja las solicitudes GET para la página principal
    response = render(request=request, template='index', files_translate=['guest'])  # English: Renders the 'index' template with guest translations | Español: Renderiza la plantilla 'index' con traducciones para invitados
    return response  # English: Returns the response | Español: Devuelve la respuesta

# Define a route for rendering a markdown file with specific styles
@router.route(path='/markdown', methods=['GET'])  # English: Handles GET requests to the '/markdown' route | Español: Maneja las solicitudes GET para la ruta '/markdown'
async def home(request: Request):  # English: Handles GET requests to the '/markdown' route | Español: Maneja las solicitudes GET para la ruta '/markdown'
    css = ["/public/css/app.css"]  # English: Define a list of CSS files to include in the response | Español: Define una lista de archivos CSS para incluir en la respuesta
    response = renderMarkdown(request=request, file='test', css_files=css, picocss=True)  # English: Renders a markdown file with PicoCSS styling | Español: Renderiza un archivo markdown con el estilo PicoCSS
    return response  # English: Returns the response | Español: Devuelve la respuesta

# Define the login route that renders the login form for authenticated users
@router.route(path='/login', methods=['GET'])  # English: Handles GET requests to the login page | Español: Maneja las solicitudes GET para la página de login
@session_active  # English: This middleware checks if the session is active | Español: Este middleware verifica si la sesión está activa
async def login(request: Request):  # English: Handles GET requests to the login page | Español: Maneja las solicitudes GET para la página de login
    response = render(request=request, template='auth/login', files_translate=['guest'])  # English: Renders the 'login' template for guests | Español: Renderiza la plantilla 'login' para los invitados
    return response  # English: Returns the response | Español: Devuelve la respuesta

# Define the registration route that renders the registration form
@router.route(path='/register', methods=['GET'])  # English: Handles GET requests to the registration page | Español: Maneja las solicitudes GET para la página de registro
@session_active  # English: This middleware checks if the session is active | Español: Este middleware verifica si la sesión está activa
async def login(request: Request):  # English: Handles GET requests to the registration page | Español: Maneja las solicitudes GET para la página de registro
    response = render(request=request, template='auth/register', files_translate=['guest'])  # English: Renders the 'register' template for guests | Español: Renderiza la plantilla 'register' para los invitados
    return response  # English: Returns the response | Español: Devuelve la respuesta

# Example middleware "login_required" (session web)
@router.route(path='/dashboard', methods=['GET'])  # English: Define the route to the dashboard, requiring an active login | Español: Define la ruta al panel de control, que requiere un login activo
@login_required  # English: This middleware checks if the user is logged in | Español: Este middleware verifica si el usuario está logueado
async def dashboard(request: Request):  # English: Handles GET requests to the dashboard page | Español: Maneja las solicitudes GET para la página del panel de control
    response = render(request=request, template='dashboard', files_translate=['authenticated'])  # English: Renders the 'dashboard' template for authenticated users | Español: Renderiza la plantilla 'dashboard' para usuarios autenticados
    return response  # English: Returns the response | Español: Devuelve la respuesta

# Delete cookie for session
@router.route(path='/logout', methods=['GET'])  # English: Defines the logout route that deletes session cookies | Español: Define la ruta de logout que elimina las cookies de sesión
async def logout(request: Request):  # English: Handles GET requests to log the user out | Español: Maneja las solicitudes GET para cerrar la sesión del usuario
    response = RedirectResponse(url='/')  # English: Creates a redirect response to the homepage | Español: Crea una respuesta de redirección a la página de inicio
    response.delete_cookie("session")  # English: Deletes the session cookie | Español: Elimina la cookie de sesión
    response.delete_cookie("auth")  # English: Deletes the authentication cookie | Español: Elimina la cookie de autenticación
    response.delete_cookie("admin")  # English: Deletes the admin cookie | Español: Elimina la cookie de administrador
    return response  # English: Returns the response | Español: Devuelve la respuesta

# Change language (session)
@router.route(path='/set-language/{lang}', methods=['GET'])  # English: Defines a route to change the language in the session | Español: Define una ruta para cambiar el idioma en la sesión
async def set_language(request: Request):  # English: Handles GET requests to change the language | Español: Maneja las solicitudes GET para cambiar el idioma
    lang = request.path_params.get('lang', LANG_DEFAULT)  # English: Gets the language from the path parameters, falling back to the default if not found | Español: Obtiene el idioma de los parámetros de la ruta, usando el valor por defecto si no se encuentra
    if not lang:  # English: Checks if the language is not set in the path | Español: Verifica si el idioma no está configurado en la ruta
        lang = request.query_params.get('lang', LANG_DEFAULT)  # English: Falls back to the query parameters for language | Español: Usa los parámetros de la consulta para obtener el idioma
    referer = request.headers.get('Referer', '/')  # English: Gets the referer header to redirect back to the original page | Español: Obtiene el encabezado 'Referer' para redirigir a la página original
    response = RedirectResponse(url=referer)  # English: Creates a redirect response to the referer URL | Español: Crea una respuesta de redirección a la URL del referer
    Session.setSession(name_cookie='lang', new_val=lang, response=response)  # English: Sets the language session cookie | Español: Configura la cookie de sesión para el idioma
    return response  # English: Returns the response | Español: Devuelve la respuesta

routes = router.get_routes()  # English: Get all the defined routes | Español: Obtiene todas las rutas definidas
