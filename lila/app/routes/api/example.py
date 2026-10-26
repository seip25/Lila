from lila.core.request import Request
from lila.core.routing import Router, EmailStr
from pydantic import BaseModel

router = Router(prefix="/api/v1")

class ExampleModel(BaseModel):
    email: EmailStr
    password: str

@router.post("/example", model=ExampleModel)
async def example(request: Request, data: ExampleModel = None):
    """
    Example POST endpoint with Pydantic v2 validation.
    In Lila v2.0, the validated model is available via dependency injection or request.state.data,
    and dict responses are automatically wrapped into JSONResponse.
    """
    model_data = data or getattr(request.state, "data", None)
    return {
        "success": True,
        "email": model_data.email if model_data else None,
        "message": "Validated successfully with Pydantic v2"
    }

routes = router.get_routes()
