from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.routing import Router
from pydantic import EmailStr, BaseModel

# English: Use the same router prefix as index.py so all api/v1 routes share the same base.
# Español: Usa el mismo prefijo que index.py para que todas las rutas api/v1 compartan la misma base.
router = Router(prefix="api/v1")


# English: Example data model using Pydantic.
# Español: Ejemplo de modelo de datos usando Pydantic.
class ExampleModel(BaseModel):
    email: EmailStr  # English: Ensures the email is valid. | Español: Garantiza que el email sea válido.
    password: str    # English: A plain string for the password. | Español: Una cadena simple para la contraseña.


# English: Defines an "api/v1/example" route, using ExampleModel for input validation,
#          with automatic documentation via the "model" parameter.
# Español: Define una ruta "api/v1/example", utilizando ExampleModel para la validación de entradas,
#          con documentación automática pasando el parámetro "model".
@router.post(path="/example", model=ExampleModel)
async def example(request: Request):
    """Example POST endpoint — shows how to use Pydantic validation with the router"""
    input = request.state.data
    return JSONResponse({"email": input.email, "password": input.password, "success": True})


routes = router.get_routes()
