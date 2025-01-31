from core.session import Session
from core.responses import RedirectResponse,JSONResponse
from core.request import Request
from functools import wraps 
from core.helpers import get_token

def login_required(func,key:str='auth',url_return='/login'):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data= Session.unsign(key=key,request=request)
        if not session_data:
            return RedirectResponse(url=url_return)
        return await func(request,*args,**kwargs)
    return wrapper

def session_active(func,key:str='auth',url_return:str ='/dashboard'):
    @wraps(func)
    async def wrapper(request,*args,**kwargs):
        session_data= Session.unsign(key=key,request=request)
        if session_data:
            return RedirectResponse(url=url_return)
        return await func(request,*args,**kwargs)
    return wrapper

def validate_token(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return JSONResponse({'session':False,'message': 'Invalid token'},status_code=401)
        
        token = get_token(token=token)
        if isinstance(token,JSONResponse):
            return token
        return await func(request, *args, **kwargs)
       
    return wrapper
