from core.env import THEME_DEFAULT, LANG_DEFAULT, SECRET_KEY
from core.session import Session
from core.request import Request
from core.responses import JSONResponse
from core.logger import Logger
import json
from pathlib import Path
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta,date
from typing import Union, List, Set

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


ALLOWED_EXTENSIONS_ = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE_ = 10 * 1024 * 1024  # 10MB
UPLOAD_DIR_ = "uploads"
async def upload(
    request: Request,
    name_file: Union[str, List[str]] = 'file',
    UPLOAD_DIR: str = UPLOAD_DIR_,
    ALLOWED_EXTENSIONS: Set[str] = ALLOWED_EXTENSIONS_,
    MAX_FILE_SIZE: int = MAX_FILE_SIZE_
):
    """
    # English: Handles file upload with validations and translations
    # Español: Maneja la subida de archivos con validaciones y traducciones
    """
    try:
        # English: Validate HTTP method
        # Español: Validar método HTTP
        if request.method != "POST":
            return JSONResponse({
                "error": True,
                "success": False,
                "message": translate_("invalid_method", request)
            }, status_code=405)

        # English: Validate content type
        # Español: Validar tipo de contenido
        content_type = request.headers.get('content-type', '')
        if 'multipart/form-data' not in content_type:
            return JSONResponse({
                "error": True,
                "success": False,
                "message": translate_("invalid_content_type", request)
            }, status_code=400)

        # English: Create upload directory if it doesn't exist
        # Español: Crear directorio de uploads si no existe
        upload_path = Path(UPLOAD_DIR)
        if not upload_path.exists():
            upload_path.mkdir(parents=True, exist_ok=True)

        try:
            form = await request.form()
            file = form.get(name_file)
            
            # English: Check if file exists in form
            # Español: Verificar si el archivo existe en el formulario
            if not file:
                return JSONResponse({
                    "error": True,
                    "success": False,
                    "message": translate_("file_not_found", request)
                }, status_code=400)

            # English: Handle multiple files
            # Español: Manejar múltiples archivos
            if isinstance(file, list):
                files = []
                for f in file:
                    # English: Validate file extension
                    # Español: Validar extensión del archivo
                    extension = f.filename.split(".")[-1].lower()
                    if extension not in ALLOWED_EXTENSIONS:
                        return JSONResponse({
                            "error": True,
                            "success": False,
                            "message": translate_("invalid_extension", request)
                        }, status_code=400)

                    # English: Validate file size
                    # Español: Validar tamaño del archivo
                    if f.size > MAX_FILE_SIZE:
                        return JSONResponse({
                            "error": True,
                            "success": False,
                            "message": translate_("file_too_large", request)
                        }, status_code=400)

                    # English: Validate file is not empty
                    # Español: Validar que el archivo no esté vacío
                    content = await f.read()
                    if len(content) == 0:
                        return JSONResponse({
                            "error": True,
                            "success": False,
                            "message": translate_("empty_file", request)
                        }, status_code=400)

                    # English: Save file with safe filename
                    # Español: Guardar archivo con nombre seguro
                    safe_filename = "".join(c for c in f.filename if c.isalnum() or c in (' ', '.', '_')).rstrip()
                    file_path = upload_path / safe_filename
                    
                    with open(file_path, "wb") as fp:
                        fp.write(content)
                    files.append(str(file_path))

                return JSONResponse({
                    "files": files,
                    "success": True,
                    "message": translate_("upload_success", request)
                }, status_code=200)

            # English: Handle single file (same validations as above)
            # Español: Manejar archivo único (mismas validaciones que arriba)
            extension = file.filename.split(".")[-1].lower()
            if extension not in ALLOWED_EXTENSIONS:
                return JSONResponse({
                    "error": True,
                    "success": False,
                    "message": translate_("invalid_extension", request)
                }, status_code=400)

            if file.size > MAX_FILE_SIZE:
                return JSONResponse({
                    "error": True,
                    "success": False,
                    "message": translate_("file_too_large", request)
                }, status_code=400)

            content = await file.read()
            if len(content) == 0:
                return JSONResponse({
                    "error": True,
                    "success": False,
                    "message": translate_("empty_file", request)
                }, status_code=400)

            safe_filename = "".join(c for c in file.filename if c.isalnum() or c in (' ', '.', '_')).rstrip()
            file_path = upload_path / safe_filename
            
            with open(file_path, "wb") as fp:
                fp.write(content)

            return JSONResponse({
                "file": str(file_path),
                "success": True,
                "message": translate_("upload_success", request)
            }, status_code=200)

        except Exception as e:
            Logger.error(str(e))
            return JSONResponse({
                "error": True,
                "success": False,
                "message": translate_("server_error", request)
            }, status_code=400)

    except Exception as e:
        Logger.error(str(e))
        return JSONResponse({
            "error": True,
            "success": False,
            "message": translate_("server_error", request)
        }, status_code=500)
