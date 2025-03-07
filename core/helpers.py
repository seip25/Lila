from core.env import THEME_DEFAULT, LANG_DEFAULT, SECRET_KEY
from core.session import Session
from core.request import Request
from core.responses import JSONResponse
import json
from pathlib import Path
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta,date


LOCALES_PATH = Path("locales")


def theme(request: Request = None) -> str:
    if request:
        t = Session.getSession(key="theme", request=request)
        if t:
            return Session.unsign(key="theme", request=request)
    t = THEME_DEFAULT
    return t


def lang(request: Request) -> str:
    l = LANG_DEFAULT or "en"
    session_lang = Session.getSession(key="lang", request=request)
    if session_lang:
        l = Session.unsign(key="lang", request=request)
    return l


def translate(file_name: str, request: Request) -> dict:
    current_lang = lang(request)
    translations = {}
    file_path = LOCALES_PATH / f"{file_name}.json"

    try:
        with open(file=file_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
        for key, val in data.items():
            if current_lang in val:
                translations[key] = val[current_lang]
            else:
                translations[key] = key
        return translations
    except FileNotFoundError:
        print(f"{file_name}.json not found")
    except json.JSONDecodeError as e:
        print(f"{file_name} - {e}")

    return translations


def translate_(key: str, request: Request, file_name: str = "translations") -> str:
    t = translate(file_name=file_name, request=request)
    if key in t:
        msg = t[key]
        return msg if msg not in [None, ""] else key
    return key


def generate_token_value(hex:int=16) -> str:
    return hashlib.sha256(secrets.token_hex(hex).encode()).hexdigest()


def generate_token(name: str, value: str = None, minutes: int = 1440) -> str:
    options = {name: value, "exp": datetime.utcnow() + timedelta(minutes=minutes)}
    options[name] = value if value else generate_token_value()
    token = jwt.encode(options, SECRET_KEY, algorithm="HS256")
    return token


def get_token(token: str):
    try:
        token = token.strip().split(" ")
        if len(token) > 1:
            token = token[1]
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            {"session": False, "message": "Token has expired"}, status_code=401
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )

def get_user_by_token(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )
    token = get_token(token=token)
    if isinstance(token, JSONResponse):
        return token
    user_id = token.get("user_id")
    if not user_id:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )
    return user_id
    
def convert_date_to_str(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat() if value else None
    return value
