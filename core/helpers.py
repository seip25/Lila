from core.env import THEME_DEFAULT,LANG_DEFAULT,SECRET_KEY
from core.session import Session 
from core.request import Request
from core.responses import JSONResponse
import json
from pathlib import Path
import jwt
import datetime

LOCALES_PATH = Path("locales")

def theme() -> str:
    t =THEME_DEFAULT
    return t

def lang(request: Request) -> str:
    l = LANG_DEFAULT or "en"
    session_lang = Session.getSession(key="lang", request=request)
    if session_lang:
        l = Session.unsign(key='lang',request=request)
    return l

def translate(file_name: str , request: Request) -> dict: 
    current_lang = lang(request)
    translations = {}
    file_path = LOCALES_PATH / f"{file_name}.json"

    try:
        with open(file=file_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
        for key, val in data.items():
            if current_lang in val:
                translations[key]=val[current_lang]
            else: 
                translations[key]=key
        return translations
    except FileNotFoundError:
        print(f"{file_name}.json not found")
    except json.JSONDecodeError as e:
        print(f"{file_name} - {e}")
    
    return translations

def generate_token(name:str,value:str)->str :
    options={}
    options[name]=value
    options['exp']=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    token = jwt.encode(options,SECRET_KEY,algorithm='HS256')
    return token

def validate_token(request:Request):
    token = request.headers.get('Authorization')
    if not token:
        return JSONResponse({'message': 'Invalid token'}), 401
    try:
        token = token.split(" ")[1] 
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return decoded_token
    except jwt.ExpiredSignatureError:
        return JSONResponse({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return JSONResponse({'message': 'Invalid token'}), 401
