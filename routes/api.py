from core.request import Request  # English: Handles HTTP requests in the application. | Español: Maneja solicitudes HTTP en la aplicación.
from core.responses import JSONResponse  # English: Simplifies sending JSON responses. | Español: Simplifica el envío de respuestas JSON.
from core.routing import Router  # English: Manages routing for API endpoints. | Español: Administra las rutas para los puntos finales de la API.
from core.helpers import translate  # English: Provides translation utilities for multilingual support. | Español: Proporciona utilidades de traducción para soporte multilingüe.
from core.session import Session  # English: Manages user sessions, including cookies. | Español: Administra sesiones de usuario, incluyendo cookies.
from pydantic import EmailStr, BaseModel  # English: Validates and parses data models for input validation. | Español: Valida y analiza modelos de datos para la validación de entradas.
from models.user import User
import hashlib
import secrets
from core.helpers import generate_token
from middlewares.middlewares import validate_token

# English: Initialize the router instance for managing API routes. 
# Español: Inicializa la instancia del enrutador para manejar rutas de la API.
router = Router()

# English: Define an API route that supports GET and POST methods.
# Español: Define una ruta de API que soporta los métodos GET y POST.
@router.route(path='/api', methods=['GET', 'POST'])
@validate_token
async def api(request: Request):
    return JSONResponse({'api': True})  # English: Returns a simple JSON response for API verification. | Español: Devuelve una respuesta JSON simple para la verificación de la API.

# English: Example data model for login using Pydantic.
# Español: Ejemplo de modelo de datos para inicio de sesión usando Pydantic.
class LoginModel(BaseModel):
    email: EmailStr  # English: Ensures the email is valid. | Español: Garantiza que el email sea válido.
    password: str  # English: A plain string for the password. | Español: Una cadena simple para la contraseña.

# English: Define a route for user login, using the LoginModel for input validation.
# Español: Define una ruta para el inicio de sesión de usuario, utilizando LoginModel para la validación de entradas.
@router.route(path='/login', methods=['POST'], model=LoginModel)
async def login(request: Request):
    """Login function"""
    msg = translate(file_name='guest', request=request)  # English: Load translations for error messages. | Español: Carga traducciones para los mensajes de error.
    msg_error = msg['Incorrect email or password']  # English: Predefined error message for invalid credentials. | Español: Mensaje de error predefinido para credenciales no válidas.
    body = await request.json()  # English: Asynchronously parse JSON body from the request. | Español: Analiza asíncronamente el cuerpo JSON de la solicitud.
    try:
        input = LoginModel(**body)  # English: Validate input data against the LoginModel. | Español: Valida los datos de entrada contra LoginModel.
    except Exception as e:
        return JSONResponse({"success": False, "msg": f"Invalid JSON Body: {e}"}, status_code=400)  # English: Return error if validation fails. | Español: Devuelve un error si la validación falla.
    
    email = input.email
    password = input.password
    check_login = User.check_login(email=email)
    if not check_login ==None:
        user = check_login
        password_db = user[2]
            
        if User.validate_password(password_db, password):
            token_db=user[1] or 'auth'
            token_jwt =generate_token(name='token',value=token_db)
            response = JSONResponse({"success": True, "msg": "success","token":token_jwt})
            
            user_id=user[0]
            token = f"{user_id}-{token_db}"
             
            Session.setSession(
                new_val=token, name_cookie="auth", response=response
            )
            return response
            
    # English: Check if email and password match predefined values (mock login validation).
    # Español: Verifica si el email y la contraseña coinciden con valores predefinidos (validación de inicio de sesión simulada).
    elif email == "example@example.com" and password == "password":
        token = hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()
        token =generate_token(name='token',value=token)
        response = JSONResponse({"success": True, "email": email, "password": password, "msg": msg_error,"token":token})
        Session.setSession(new_val='auth', name_cookie='auth', response=response)  # English: Set a session cookie if login is successful. | Español: Establece una cookie de sesión si el inicio de sesión es exitoso.
        return response
    response = JSONResponse({"success": False, "msg": msg_error})
    return response

# English: Example data model for user registration using Pydantic.
# Español: Ejemplo de modelo de datos para el registro de usuarios usando Pydantic.
class RegisterModel(BaseModel):
    email: EmailStr  # English: Validates the email format. | Español: Valida el formato del email.
    password: str  # English: Password input for the user. | Español: Contraseña ingresada por el usuario.
    name: str  # English: Name of the user. | Español: Nombre del usuario.
    password_2: str  # English: Confirmation password. | Español: Confirmación de contraseña.

# English: Define a route for user registration, using the RegisterModel for input validation.
# Español: Define una ruta para el registro de usuario, utilizando RegisterModel para la validación de entradas.
@router.route(path='/register', methods=['POST'], model=RegisterModel)
async def register(request: Request):
    """Register function"""
    body = await request.json()
    password = body["password"]
    password_2 = body["password_2"]
    t = translate(file_name="translations", request=request)
    if password != password_2:
        msg = t["Passwords not match"]
        response = JSONResponse({"success": False, "msg": msg})
        return response
    try:
        input = RegisterModel(**body)  # English: Validate input data against the RegisterModel. | Español: Valida los datos de entrada contra RegisterModel.
    except Exception as e:
        return JSONResponse({"success": False, "msg": f"Invalid JSON Body: {e}"}, status_code=400)
    
    name = input.name
    email = input.email
    password = input.password
    duplicated = User.check_email(email=email)
    if duplicated:
        msg = t["Error creating account,check email"]
        response = JSONResponse({"success": False, "msg": msg})
        return response
    result = User.insert({"name": name, "email": email, "password": password})
    if result:
        token = result
        response = JSONResponse({"success": True})
        Session().setSession(new_val=token, response=response, name_cookie="auth")
        return response
    else:
        msg = t["Error creating account"]
        response = JSONResponse({"success": False, "msg": msg})
        return response


# English: Enable Swagger UI for API documentation.
# Español: Habilita Swagger UI para la documentación de la API.
router.swagger_ui()

# English: Generate OpenAPI JSON for external tools.
# Español: Genera JSON de OpenAPI para herramientas externas.
router.openapi_json()

# English: Retrieve all defined routes in the application.
# Español: Obtiene todas las rutas definidas en la aplicación.
routes = router.get_routes()
