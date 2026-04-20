from app.config import LANG_DEFAULT, PATH_LOCALES, DEBUG
from core.session import Session
from core.request import Request
from pathlib import Path
import orjson

_TRANSLATIONS_CACHE: dict[str, dict] = {}

class Translate:
    @staticmethod
    def load_translations(file_name: str) -> dict:
        """Loads translations from a JSON file with caching."""
        if file_name in _TRANSLATIONS_CACHE:
            return _TRANSLATIONS_CACHE[file_name]

        file_path = Path(PATH_LOCALES) / f"{file_name}.json"
        try:
            from core.responses import orjson_loads
            with open(file_path, "rb") as f:
                data = orjson_loads(f.read())
            _TRANSLATIONS_CACHE[file_name] = data
            return data
        except Exception:
            _TRANSLATIONS_CACHE[file_name] = {}
            if DEBUG:
                print(f"Error loading translations for {file_name}")
            return {}

    @staticmethod
    def lang(request: Request) -> str:
        """Retrieves the current language from the session or default config."""
        l = LANG_DEFAULT or "en"
        session_lang = Session.getSessionValue(key="lang", request=request)
        return session_lang if session_lang else l

    @staticmethod
    def get_translations(file_name: str, request: Request, lang_default: str = None) -> dict:
        """Returns a dictionary of translations for the current language."""
        current_lang = lang_default if lang_default else Translate.lang(request)
        data = Translate.load_translations(file_name)
        return {k: v.get(current_lang, k) for k, v in data.items()}

    @staticmethod
    def t(key: str, request: Request, file_name: str = "translations", lang_default: str = None) -> str:
        """Translates a specific key."""
        translations = Translate.get_translations(file_name, request, lang_default)
        return translations.get(key, key)

    @staticmethod
    async def set_lang(request: Request, response, new_lang: str) -> None:
        """Sets the language in the session cookie."""
        Session.setSession(new_val=new_lang, response=response, name_cookie="lang")

    @staticmethod
    def translate_pydantic_error(error: dict, target_lang: str) -> str:
        """Translates Pydantic validation errors into Spanish if target_lang is 'es'."""
        if target_lang != "es":
            return error["msg"]
        
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
            "value_error.email.code":"Formato de correo electrónico no válido"
        }
        
        err_type = error.get("type")
        msg = PYDANTIC_MESSAGES_ES.get(err_type, error.get("msg"))
        if "ctx" in error:
            try:
                return msg.format(**error["ctx"])
            except:
                pass
        return msg
