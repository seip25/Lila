from app.config import LANG_DEFAULT, PATH_LOCALES, DEBUG
from lila.core.request import Request
from pathlib import Path
import os

_TRANSLATIONS_CACHE: dict[str, dict] = {}


class Translate:
    """
    Lightweight translation and internationalization utility for Lila Framework.
    Supports language detection via query param (?lang=), request body, Accept-Language header, or cookies.
    """

    translate_enabled = True

    @staticmethod
    def load_translations(file_name: str = "translate") -> dict:
        """
        Loads translations from an optional user JSON file in app/locales/{file_name}.json.
        Returns an empty dict if the file does not exist.
        """
        if file_name in _TRANSLATIONS_CACHE and not DEBUG:
            return _TRANSLATIONS_CACHE[file_name]

        locales_dir = getattr(Translate, "path_locales", PATH_LOCALES)
        file_path = Path(locales_dir) / f"{file_name}.json"
        
        if not file_path.exists():
            _TRANSLATIONS_CACHE[file_name] = {}
            return {}

        try:
            from lila.core.responses import orjson_loads
            with open(file_path, "rb") as f:
                data = orjson_loads(f.read())
            _TRANSLATIONS_CACHE[file_name] = data
            return data
        except Exception as e:
            if DEBUG:
                print(f"Error loading translations from {file_path}: {e}")
            _TRANSLATIONS_CACHE[file_name] = {}
            return {}

    @staticmethod
    def lang(request: Request) -> str:
        """
        Determines the client's language preference.
        Precedence:
          1. Query parameter: ?lang=es
          2. Body field: {"lang": "es"} (if available in request.state.data)
          3. Accept-Language header
          4. Cookie: lang
          5. Default language (LANG_DEFAULT / "en")
        """
        if hasattr(request, "state") and hasattr(request.state, "lang") and request.state.lang:
            return request.state.lang

        # 1. Query parameter
        if hasattr(request, "query_params"):
            query_lang = request.query_params.get("lang")
            if query_lang:
                request.state.lang = query_lang.lower().strip()
                return request.state.lang

        # 2. Body field (if parsed into request.state.data)
        if hasattr(request, "state") and hasattr(request.state, "data"):
            data = request.state.data
            if isinstance(data, dict) and "lang" in data:
                request.state.lang = str(data["lang"]).lower().strip()
                return request.state.lang
            elif hasattr(data, "lang") and getattr(data, "lang"):
                request.state.lang = str(getattr(data, "lang")).lower().strip()
                return request.state.lang

        # 3. Accept-Language header
        if hasattr(request, "headers"):
            accept_lang = request.headers.get("accept-language")
            if accept_lang:
                primary = accept_lang.split(",")[0].split(";")[0].strip().lower()
                lang_code = primary[:2]
                if lang_code in ("es", "en", "pt", "fr", "de", "it"):
                    request.state.lang = lang_code
                    return request.state.lang

        # 4. Cookie
        if hasattr(request, "cookies"):
            cookie_lang = request.cookies.get("lang")
            if cookie_lang:
                clean_cookie = cookie_lang.split(".")[0].strip().lower()
                request.state.lang = clean_cookie
                return request.state.lang

        # 5. Default
        fallback = LANG_DEFAULT or "en"
        if hasattr(request, "state"):
            request.state.lang = fallback
        return fallback

    @staticmethod
    def t(key: str, request: Request = None, file_name: str = "translate", default: str = None) -> str:
        """
        Translates a key for the current request language from app/locales/{file_name}.json.
        Falls back to default or the key string itself if not found.
        """
        current_lang = Translate.lang(request) if request else (LANG_DEFAULT or "en")
        translations = Translate.load_translations(file_name)
        
        if key in translations:
            val = translations[key]
            if isinstance(val, dict):
                return val.get(current_lang, default or key)
            return str(val)

        return default if default is not None else key

    @staticmethod
    def translate_pydantic_error(error: dict, target_lang: str = "en") -> str:
        """Translates common Pydantic validation errors into Spanish if target_lang is 'es'."""
        if target_lang != "es":
            return error.get("msg", "Validation error")

        pydantic_messages_es = {
            "field required": "Este campo es obligatorio",
            "missing": "Falta este campo",
            "value_error.missing": "Falta este campo",
            "string_too_short": "Debe tener al menos {min_length} caracteres",
            "string_too_long": "No puede superar los {max_length} caracteres",
            "string_type": "Debe ser una cadena de texto",
            "value_is_not_a_valid_integer": "Debe ser un número entero válido",
            "value_is_not_a_valid_email": "Formato de correo electrónico no válido",
            "value_error.email": "Formato de correo electrónico no válido",
        }

        err_type = error.get("type", "")
        msg = pydantic_messages_es.get(err_type, error.get("msg", "Error de validación"))
        if "ctx" in error:
            try:
                return msg.format(**error["ctx"])
            except Exception:
                pass
        return msg
