from core.request import Request  # English: Handles HTTP requests in the application. | Español: Maneja solicitudes HTTP en la aplicación.
from core.responses import JSONResponse  # English: Simplifies sending JSON responses. | Español: Simplifica el envío de respuestas JSON.
from core.routing import Router  # English: Manages routing for API endpoints. | Español: Administra las rutas para los puntos finales de la API.
from pydantic import EmailStr, BaseModel  # English: Validates and parses data models for input validation. | Español: Valida y analiza modelos de datos para la validación de entradas.
from core.helpers import get_user_by_id_and_token
from middlewares.middlewares import validate_token

# English: Initialize the router instance for managing API routes. 
# Español: Inicializa la instancia del enrutador para manejar rutas de la API.
router = Router()


# English: Define a simple API route that supports GET method.
# Español: Define una ruta de API simple que soporta el método GET.
@router.route(path='/api', methods=['GET'])
async def api(request: Request):
    """Api function"""#use doc for descripction http://127.0.0.1:8000/openapi.json and http://127.0.0.1:8000/docs
    # English: Returns a simple JSON response for API verification. | Español: Devuelve una respuesta JSON simple para la verificación de la API.
    return JSONResponse({'api': True})  

# English: Define an API route that supports GET and POST methods.
# Español: Define una ruta de API que soporta los métodos GET y POST.
@router.route(path='/api/token', methods=['GET','POST'])
# English: Middleware to validate the JWT Token.
# Español: Middleware para validar token de JWT.
@validate_token
async def api_token(request: Request):
    """Api Token function"""#use doc for descripction http://127.0.0.1:8000/openapi.json and http://127.0.0.1:8000/docs
    print(get_user_by_id_and_token(request=request))
    return JSONResponse({'api': True}) 


# English: Example data model using Pydantic.
# Español: Ejemplo de modelo de datos usando Pydantic.
class ExampleModel(BaseModel):
    email: EmailStr  # English: Ensures the email is valid. | Español: Garantiza que el email sea válido.
    password: str  # English: A plain string for the password. | Español: Una cadena simple para la contraseña.

# English: Defines an "api/example" route, using ExampleModel for input validation, with automatic documentation passing the "model" parameter ("model=ExampleModel").
# Español: Define una ruta "api/example", utilizando ExampleModel para la validación de entradas,con documentación automatica pasandole el parametro "model"("model=ExampleModel")
@router.route(path='/api/example', methods=['POST'], model=ExampleModel)
async def login(request: Request):
    """Example function"""#use doc for descripction http://127.0.0.1:8000/openapi.json and http://127.0.0.1:8000/docs
    # English: Asynchronously parse JSON body from the request. 
    # Español: Analiza asíncronamente el cuerpo JSON de la solicitud.
    body = await request.json()  
    try:
        # English: Validate input data against the ExampleModel. 
        # Español: Valida los datos de entrada contra ExampleModel.
        input = ExampleModel(**body) 
    except Exception as e:
        return JSONResponse({"success": False, "msg": f"Invalid JSON Body: {e}"}, status_code=400) 
    
    email = input.email
    password = input.password
    response= JSONResponse({"email": email, "password": password})
    return response



from database.connections import connection
from models.user import User
from pydantic import BaseModel, EmailStr


class UserModel(BaseModel):
    email: EmailStr
    name: str
    token: str
    password: str


router.rest_crud_generate(
    connection=connection,
    model_sql=User,
    model_pydantic=UserModel,
    select=["name", "email", "id", "created_at", "active"],
    delete_logic=True,
    active=True,
)


# English: Enable Swagger UI for API documentation.
# Español: Habilita Swagger UI para la documentación de la API.
router.swagger_ui()

# English: Generate OpenAPI JSON for external tools.
# Español: Genera JSON de OpenAPI para herramientas externas.
router.openapi_json()

# English: Retrieve all defined routes in the application.
# Español: Obtiene todas las rutas definidas en la aplicación.
routes = router.get_routes()
