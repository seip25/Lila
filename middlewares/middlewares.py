from core.session import Session
from core.responses import RedirectResponse, JSONResponse
from core.request import Request
from functools import wraps
from core.helpers import get_token,generate_token


def login_required(func, key: str = "auth", url_return="/login"):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data = await check_session(request=request, key=key)
        if not session_data:
            return RedirectResponse(url=url_return)
        return await func(request, *args, **kwargs)

    return wrapper


def session_active(func, key: str = "auth", url_return: str = "/dashboard"):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data = await check_session(request=request, key=key)
        if session_data:
            return RedirectResponse(url=url_return)
        return await func(request, *args, **kwargs)

    return wrapper


async def check_session(request: Request, key: str='auth', return_JsonResponse: bool = False):
    session_data = Session.unsign(key=key, request=request)
    if return_JsonResponse:
        return JSONResponse({"session": False, "success": False}, status_code=401)
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
    token = request.headers.get("Authorization")
    if not token:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )
    print(generate_token(name='token',value='token'))
    token = get_token(token=token)
    if isinstance(token, JSONResponse):
        return token
    return True
