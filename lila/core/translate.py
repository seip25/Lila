from app.config import LANG_DEFAULT, PATH_LOCALES, DEBUG
from lila.core.session import Session
from lila.core.request import Request
from pathlib import Path
import orjson

_TRANSLATIONS_CACHE: dict[str, dict] = {}

class Translate:
    """
    Core translation utility class for loading, caching, and retrieving translations.
    Clase de utilidad de traducción central para cargar, almacenar en caché y recuperar traducciones.
    """
    _PROCESSED_CACHE: dict[str, dict[str, dict]] = {}
    translate_enabled = True

    @staticmethod
    def load_translations(file_name: str) -> dict:
        """
        Loads translations from a JSON file with caching.
        Carga las traducciones desde un archivo JSON con almacenamiento en caché.
        """
        if file_name in _TRANSLATIONS_CACHE:
            return _TRANSLATIONS_CACHE[file_name]

        if not getattr(Translate, "translate_enabled", True) and file_name == "translations":
            _TRANSLATIONS_CACHE[file_name] = {}
            return {}

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

    @staticmethod
    def lang(request: Request) -> str:
        """
        Retrieves the current language from the cookie or default config, using request state as cache.
        Recupera el idioma actual desde la cookie o la configuración por defecto, utilizando el estado de la solicitud como caché.
        """
        if hasattr(request.state, "lang"):
            return request.state.lang

        cookie_lang = request.cookies.get("lang")
        if cookie_lang:
            if "." in cookie_lang:
                session_lang = Session.getSessionValue(key="lang", request=request)
                if session_lang:
                    request.state.lang = session_lang
                    return session_lang
            else:
                request.state.lang = cookie_lang
                return cookie_lang

        l = LANG_DEFAULT or "en"
        request.state.lang = l
        return request.state.lang

    @staticmethod
    def get_translations(file_name: str, request: Request, lang_default: str = None) -> dict:
        """
        Returns a dictionary of translations for the current language, with internal caching.
        Devuelve un diccionario de traducciones para el idioma actual, con almacenamiento en caché interno.
        """
        current_lang = lang_default if lang_default else Translate.lang(request)
        
        if file_name in Translate._PROCESSED_CACHE and current_lang in Translate._PROCESSED_CACHE[file_name]:
            if not DEBUG:
                return Translate._PROCESSED_CACHE[file_name][current_lang]

        data = Translate.load_translations(file_name)
        
        if file_name == "translations":
            try:
                from lila.core.translate_defaults import CORE_TRANSLATIONS
                processed = {k: v.get(current_lang, k) for k, v in CORE_TRANSLATIONS.items()}
                user_processed = {k: v.get(current_lang, k) for k, v in data.items()}
                processed.update(user_processed)
            except Exception:
                processed = {k: v.get(current_lang, k) for k, v in data.items()}
        elif file_name == "changelogs":
            try:
                from lila.core.translate_defaults import CORE_CHANGELOGS
                processed = {k: v.get(current_lang, k) for k, v in CORE_CHANGELOGS.items()}
                user_processed = {k: v.get(current_lang, k) for k, v in data.items()}
                processed.update(user_processed)
            except Exception:
                processed = {k: v.get(current_lang, k) for k, v in data.items()}
        else:
            processed = {k: v.get(current_lang, k) for k, v in data.items()}
        
        if file_name not in Translate._PROCESSED_CACHE:
            Translate._PROCESSED_CACHE[file_name] = {}
        Translate._PROCESSED_CACHE[file_name][current_lang] = processed
        
        return processed

    @staticmethod
    def t(key: str, request: Request, file_name: str = "translations", lang_default: str = None) -> str:
        """
        Translates a specific key.
        Traduce una clave específica.
        """
        translations = Translate.get_translations(file_name, request, lang_default)
        return translations.get(key, key)

    @staticmethod
    async def set_lang(request: Request, response, new_lang: str) -> None:
        """
        Sets the language in a plain cookie directly to bypass cryptographic signature overhead.
        Establece el idioma en una cookie simple directamente para evitar la sobrecarga de la firma criptográfica.
        """
        response.set_cookie(
            key="lang",
            value=new_lang,
            max_age=3600 * 24 * 365,
            secure=True,
            httponly=False,
            samesite="lax",
        )
        request.state.lang = new_lang

    @staticmethod
    def translate_pydantic_error(error: dict, target_lang: str) -> str:
        """
        Translates Pydantic validation errors into Spanish if target_lang is 'es'.
        Traduce los errores de validación de Pydantic al español si target_lang es 'es'.
        """
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
