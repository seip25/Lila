from app.config import  LANG_DEFAULT, PATH_LOCALES,DEBUG
from lila.core.session import Session
from lila.core.request import Request 
import orjson
from pathlib import Path 

_TRANSLATIONS_CACHE: dict[str, dict] = {}

def load_translations(file_name: str) -> dict:
    if file_name in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[file_name]

    file_path = Path(PATH_LOCALES) / f"{file_name}.json"
    try:
        from lila.core.responses import orjson_loads
        with open(file_path, "rb") as f:
            data = orjson_loads(f.read())
        _TRANSLATIONS_CACHE[file_name] = data 
        return data
    except Exception:
        _TRANSLATIONS_CACHE[file_name] = {}
        if DEBUG:
            print(f"Error loading translations for {file_name}")
        return {}

def lang(request: Request) -> str:
    l = LANG_DEFAULT or "en"
    session_lang = Session.getSessionValue(key="lang", request=request) 
    if session_lang:
        l = Session.unsign(key="lang", request=request) 
    return l

def translate(file_name: str, request: Request, lang_default: str = None) -> dict:
    current_lang = lang(request) if not lang_default else lang_default
    data = load_translations(file_name)
    translations = {k: v.get(current_lang, k) for k, v in data.items()}
    return translations


def translate_(
    key: str,
    request: Request,
    file_name: str = "translations",
    lang_default: str = None,
) -> str:
    t = translate(file_name=file_name, request=request, lang_default=lang_default)
    if key in t:
        msg = t[key]
        return msg if msg not in [None, ""] else key
    return key

async def set_lang(request: Request, lang: str) ->None:
    Session.setSessionValue(key="lang", value=lang, request=request)
    
PYDANTIC_MESSAGES_ES = {
    "field required": "Este campo es obligatorio",
    "value_error.missing": "Falta este campo",
    "value_error.number.not_gt": "El valor debe ser mayor a {limit_value}",
    "string_too_short": "Debe tener al menos {min_length} caracteres",
    "string_too_long": "No puede superar los {max_length} caracteres",
    "value_is_not_a_valid_integer": "Debe ser un número entero válido",
    "value_is_not_a_valid_email": "Formato de correo electrónico no válido",
    "missing":"Falta este campo",
    "string_type":"Debe ser una cadena de texto",
    "string_min_length":"Debe tener al menos {min_length} caracteres",
    "string_max_length":"No puede superar los {max_length} caracteres",
    "value_error.any_str.min_length":"Debe tener al menos {min_length} caracteres",
    "value_error.any_str.max_length":"No puede superar los {max_length} caracteres",
    "value_error.email":"Formato de correo electrónico no válido",
    "value_error.email.code":"Formato de correo electrónico no válido",
    "value_error.email.code":"Formato de correo electrónico no válido"
}

def translate_pydantic_error(error: dict, target_lang: str) -> str:
    if target_lang != "es":
        return error["msg"]
    
    err_type = error.get("type")
    msg = PYDANTIC_MESSAGES_ES.get(err_type, error.get("msg"))
    if "ctx" in error:
        try:
            return msg.format(**error["ctx"])
        except:
            pass
    return msg