from app.config import   SECRET_KEY 
from lila.core.request import Request
from lila.core.responses import JSONResponse 
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

 

def generate_token_value(hex: int = 16) -> str:
    return hashlib.sha256(secrets.token_hex(hex).encode()).hexdigest()


def generate_token(name: str, value: str = None, minutes: int = 1440) -> str:
    options = {name: value, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}
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


def get_user_by_token(request: Request,key:str="user_id"):
    token = request.headers.get("Authorization")
    if not token:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )
    token = get_token(token=token)
    if isinstance(token, JSONResponse):
        return token
    user_id = token.get(key)
    if not user_id:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )
    return user_id
