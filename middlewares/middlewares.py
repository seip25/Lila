from core.session import Session
from core.responses import RedirectResponse,JSONResponse
from core.env import SECRET_KEY
from core.request import Request
from functools import wraps 
import jwt

def login_required(func,key:str='auth'):
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        session_data= Session.unsign(key=key,request=request)
        if not session_data:
            return RedirectResponse(url='/login')
        return await func(request,*args,**kwargs)
    return wrapper

def validate_token(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return JSONResponse({'message': 'Invalid token'},status_code=401)
        try:
            token = token.split(" ")[1] 
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return await func(request, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return JSONResponse({'message': 'Token has expired'}, status_code=401) 
        except jwt.InvalidTokenError:
            return JSONResponse({'message': 'Invalid token'},status_code=401)

    return wrapper