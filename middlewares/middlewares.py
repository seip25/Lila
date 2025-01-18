from core.session import Session
from core.responses import RedirectResponse
from functools import wraps

def login_required(func,key:str='auth'):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data= Session.unsign(key=key,request=request)
        if not session_data:
            return RedirectResponse(url='/login')
        return await func(request,*args,**kwargs)
    return wrapper

def check_token(func):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        #Validate token and id for headers in db or use jwt 
        return await func(request,*args,**kwargs)
    return wrapper
