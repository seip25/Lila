from app.config import SECRET_KEY
from lila.core.request import Request
from lila.core.responses import JSONResponse
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Union, Any


def generate_token_value(hex_length: int = 16) -> str:
    """Generates a secure random token value."""
    return hashlib.sha256(secrets.token_hex(hex_length).encode()).hexdigest()


def generate_token(name: str, value: Any = None, minutes: int = 1440) -> str:
    """Generates a JWT token with an expiration time."""
    options = {
        name: value if value is not None else generate_token_value(),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)
    }
    return jwt.encode(options, SECRET_KEY, algorithm="HS256")


def get_token(token_str: str) -> Union[dict, JSONResponse]:
    """Decodes and validates a JWT token."""
    try:
        if " " in token_str:
            token_str = token_str.strip().split(" ")[1]
        
        return jwt.decode(token_str, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            {"session": False, "message": "Token has expired"}, status_code=401
        )
    except jwt.InvalidTokenError:
        return JSONResponse(
            {"session": False, "message": "Invalid token"}, status_code=401
        )


def get_user_id_by_token(request: Request, key: str = "user_id") -> Any:
    """Extracts the user ID from the Authorization header token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            {"session": False, "message": "Missing Authorization header"}, status_code=401
        )
    
    token_data = get_token(auth_header)
    if isinstance(token_data, JSONResponse):
        return token_data
    
    user_id = token_data.get(key)
    if user_id is None:
        return JSONResponse(
            {"session": False, "message": "User ID not found in token"}, status_code=401
        )
    return user_id
