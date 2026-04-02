from lila.core.session import Session
from lila.core.responses import RedirectResponse, JSONResponse
from lila.core.request import Request
from functools import wraps
from app.helpers.security import get_token


def login_required(func, key: str = "auth", url_return="/login"):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data = await check_session(request=request, key=key,return_JsonResponse=False)
        if not session_data:
            return RedirectResponse(url=url_return)
        return await func(request, *args, **kwargs)

    return wrapper


def session_active(func, key: str = "auth", url_return: str = "/dashboard"):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data = await check_session(request=request, key=key,return_JsonResponse=False)
        if session_data:
            return RedirectResponse(url=url_return)
        return await func(request, *args, **kwargs)

    return wrapper


async def check_session(request: Request, key: str='auth', return_JsonResponse: bool = True):
    session_data = Session.unsign(key=key, request=request)
    if not session_data:
        if return_JsonResponse:
            return JSONResponse({"session": False, "success": False}, status_code=401)
        return None
        request.state.session = session_data
    return session_data


def validate_token(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        response = await check_token(request=request)
        if isinstance(response, JSONResponse):
            return response
        return await func(request, *args, **kwargs)

    return wrapper


async def check_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            {"session": False, "message": "Missing Authorization header"}, status_code=401
        )
    
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            {"session": False, "message": "Invalid token format. Use Bearer <token>"}, status_code=401
        )

    token_str = auth_header.split(" ")[1]
    token_data = get_token(token=token_str)
    if isinstance(token_data, JSONResponse):
        return token_data
    
    request.state.user = token_data
    return True
 