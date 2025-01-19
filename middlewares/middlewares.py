from core.session import Session
from core.responses import RedirectResponse
from core.request import Request
from functools import wraps
from core.helpers import validate_token

def login_required(func,key:str='auth'):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data= Session.unsign(key=key,request=request)
        if not session_data:
            return RedirectResponse(url='/login')
        return await func(request,*args,**kwargs)
    return wrapper

def check_token(func,request=Request):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        validate_token(request=request) #jwt validate token
        return await func(request,*args,**kwargs)
    return wrapper
