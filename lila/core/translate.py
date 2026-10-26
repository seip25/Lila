"""Lila Framework v2.0.0 Lightweight Translation Engine.
Fast, in-memory Pydantic v2 validation error translation (es, en, pt)
with zero disk I/O and zero session overhead per request.
"""

from typing import Optional, Any
from lila.core.config import ENV_CONFIG


# Pydantic v2 error templates by error type
PYDANTIC_MESSAGES = {
    "es": {
        "missing": "Este campo es requerido.",
        "string_type": "Debe ser una cadena de texto válida.",
        "string_too_short": "Debe tener al menos {min_length} caracteres.",
        "string_too_long": "No puede tener más de {max_length} caracteres.",
        "string_pattern_mismatch": "El formato no coincide con el patrón requerido.",
        "int_parsing": "Debe ser un número entero válido.",
        "float_parsing": "Debe ser un número decimal válido.",
        "bool_parsing": "Debe ser un valor booleano verdadero o falso.",
        "greater_than": "El valor debe ser mayor que {gt}.",
        "greater_than_equal": "El valor debe ser mayor o igual que {ge}.",
        "less_than": "El valor debe ser menor que {lt}.",
        "less_than_equal": "El valor debe ser menor o igual que {le}.",
        "value_error": "Valor no válido.",
        "value_error.email": "Debe ser una dirección de correo electrónico válida.",
        "email": "Debe ser una dirección de correo electrónico válida.",
        "url_parsing": "Debe ser una URL válida.",
        "uuid_parsing": "Debe ser un UUID válido.",
        "date_parsing": "Debe ser una fecha válida (YYYY-MM-DD).",
        "datetime_parsing": "Debe ser una fecha y hora válida.",
        "list_type": "Debe ser una lista.",
        "dict_type": "Debe ser un objeto o diccionario válido.",
        "literal_error": "El valor debe ser uno de los permitidos.",
        "too_short": "Debe tener al menos {min_length} elementos.",
        "too_long": "No puede tener más de {max_length} elementos.",
    },
    "en": {
        "missing": "Field required.",
        "string_type": "Input should be a valid string.",
        "string_too_short": "String should have at least {min_length} characters.",
        "string_too_long": "String should have at most {max_length} characters.",
        "string_pattern_mismatch": "String should match pattern.",
        "int_parsing": "Input should be a valid integer.",
        "float_parsing": "Input should be a valid number.",
        "bool_parsing": "Input should be a valid boolean.",
        "greater_than": "Input should be greater than {gt}.",
        "greater_than_equal": "Input should be greater than or equal to {ge}.",
        "less_than": "Input should be less than {lt}.",
        "less_than_equal": "Input should be less than or equal to {le}.",
        "value_error": "Invalid value.",
        "value_error.email": "Input should be a valid email address.",
        "email": "Input should be a valid email address.",
        "url_parsing": "Input should be a valid URL.",
        "uuid_parsing": "Input should be a valid UUID.",
        "date_parsing": "Input should be a valid date.",
        "datetime_parsing": "Input should be a valid datetime.",
        "list_type": "Input should be a valid list.",
        "dict_type": "Input should be a valid dictionary.",
        "literal_error": "Input should be one of permitted values.",
        "too_short": "Should have at least {min_length} items.",
        "too_long": "Should have at most {max_length} items.",
    },
    "pt": {
        "missing": "Este campo é obrigatório.",
        "string_type": "Deve ser um texto válido.",
        "string_too_short": "Deve conter pelo menos {min_length} caracteres.",
        "string_too_long": "Não pode conter mais de {max_length} caracteres.",
        "string_pattern_mismatch": "O formato não coincide com o padrão esperado.",
        "int_parsing": "Deve ser um número inteiro válido.",
        "float_parsing": "Deve ser um número decimal válido.",
        "bool_parsing": "Deve ser verdadeiro ou falso.",
        "greater_than": "O valor deve ser maior que {gt}.",
        "greater_than_equal": "O valor deve ser maior ou igual a {ge}.",
        "less_than": "O valor deve ser menor que {lt}.",
        "less_than_equal": "O valor deve ser menor ou igual a {le}.",
        "value_error": "Valor inválido.",
        "value_error.email": "Deve ser um endereço de e-mail válido.",
        "email": "Deve ser um endereço de e-mail válido.",
        "url_parsing": "Deve ser uma URL válida.",
        "uuid_parsing": "Deve ser um UUID válido.",
        "date_parsing": "Deve ser uma data válida.",
        "datetime_parsing": "Deve ser uma data e hora válida.",
        "list_type": "Deve ser uma lista válida.",
        "dict_type": "Deve ser um dicionário válido.",
        "literal_error": "O valor deve ser um dos permitidos.",
        "too_short": "Deve ter no mínimo {min_length} itens.",
        "too_long": "Deve ter no máximo {max_length} itens.",
    },
}


class SafeTranslationDict(dict):
    """Dictionary for template translation that never raises KeyError or UndefinedError in Jinja."""

    def __init__(self, data: Optional[dict] = None, lang: str = "en") -> None:
        super().__init__(data or {})
        self.lang = lang

    def __getitem__(self, key: str) -> Any:
        val = super().get(key)
        return val if val is not None else ""

    def __missing__(self, key: str) -> str:
        return ""

    def get(self, key: str, default: Any = None) -> Any:
        val = super().get(key)
        if val is not None and val != "":
            return val
        return default if default is not None else ""


_LOCALES_CACHE: dict[str, SafeTranslationDict] = {}


class Translate:
    """Fast, zero-overhead translator specialized in Pydantic v2 validation errors and UI locales."""

    BUILTIN_LOCALES = {
        "en": {
            "login": "Welcome Back",
            "register": "Create Account",
            "email": "Email Address",
            "password": "Password",
            "confirm_password": "Confirm Password",
            "forgot_password": "Forgot Password?",
            "reset_password": "Reset Password",
            "logout": "Log Out",
            "dashboard": "Dashboard",
            "profile": "Profile",
            "welcome": "Welcome",
            "save": "Save",
            "cancel": "Cancel",
            "submit": "Submit",
            "delete": "Delete",
            "edit": "Edit",
            "create": "Create",
            "search": "Search",
            "back": "Go Back",
            "not_found": "Page Not Found",
        },
        "es": {
            "login": "Bienvenido de nuevo",
            "register": "Crear Cuenta",
            "email": "Correo Electrónico",
            "password": "Contraseña",
            "confirm_password": "Confirmar Contraseña",
            "forgot_password": "¿Olvidaste tu contraseña?",
            "reset_password": "Restablecer Contraseña",
            "logout": "Cerrar Sesión",
            "dashboard": "Panel de Control",
            "profile": "Perfil",
            "welcome": "Bienvenido",
            "save": "Guardar",
            "cancel": "Cancelar",
            "submit": "Enviar",
            "delete": "Eliminar",
            "edit": "Editar",
            "create": "Crear",
            "search": "Buscar",
            "back": "Volver",
            "not_found": "Página no encontrada",
        },
    }

    @classmethod
    def lang(cls, request: Any = None) -> str:
        """Determines requested language with fast O(1) in-memory checks."""
        if request is not None:
            # 1. Query parameter (?lang=es)
            try:
                q_lang = request.query_params.get("lang")
                if q_lang:
                    return q_lang[:2].lower()
            except Exception:
                pass

            # 2. Cookie
            try:
                c_lang = request.cookies.get("lang")
                if c_lang:
                    return c_lang[:2].lower()
            except Exception:
                pass

            # 3. Header Accept-Language
            try:
                header = request.headers.get("accept-language")
                if header:
                    return header.split(",")[0].split("-")[0].strip().lower()
            except Exception:
                pass

        # 4. Fallback from environment
        return str(ENV_CONFIG.get("LANG_DEFAULT", "en"))[:2].lower()

    @classmethod
    def get_dict(cls, lang: Optional[str] = None) -> SafeTranslationDict:
        """Returns in-memory dictionary for requested language, loading from app/locales/{lang}.json once."""
        target_lang = (lang or cls.lang())[:2].lower()
        if target_lang in _LOCALES_CACHE:
            return _LOCALES_CACHE[target_lang]

        merged = dict(cls.BUILTIN_LOCALES.get(target_lang, cls.BUILTIN_LOCALES.get("en", {})))

        # Try loading custom project JSON
        import os
        import json
        from lila.core.config import get_base_path

        candidates = [
            get_base_path("app", "locales", f"{target_lang}.json"),
            os.path.join(os.path.dirname(__file__), "..", "app", "locales", f"{target_lang}.json"),
        ]

        for cand in candidates:
            if os.path.isfile(cand):
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        custom_dict = json.load(f)
                        if isinstance(custom_dict, dict):
                            merged.update(custom_dict)
                    break
                except Exception:
                    pass

        safe_dict = SafeTranslationDict(merged, lang=target_lang)
        _LOCALES_CACHE[target_lang] = safe_dict
        return safe_dict

    @classmethod
    def translate_pydantic_error(cls, error: dict, target_lang: str = "es") -> str:
        """Translates a single Pydantic v2 error dictionary to the target language."""
        lang_key = target_lang[:2].lower()
        if lang_key not in PYDANTIC_MESSAGES:
            lang_key = "en" if "en" in PYDANTIC_MESSAGES else "es"

        catalog = PYDANTIC_MESSAGES.get(lang_key, PYDANTIC_MESSAGES["es"])
        err_type = error.get("type", "")
        ctx = error.get("ctx", {}) or {}

        template = catalog.get(err_type)
        if not template:
            for k, tmpl in catalog.items():
                if err_type.startswith(k) or k.startswith(err_type):
                    template = tmpl
                    break

        if template:
            try:
                return template.format(**ctx)
            except Exception:
                return template

        return error.get("msg", "Invalid value")

    @classmethod
    def format_errors(cls, validation_exception: Any, request: Any = None) -> list[dict]:
        """Formats all Pydantic errors into translated field -> message mapping."""
        target_lang = cls.lang(request)
        translated = []
        try:
            for err in validation_exception.errors():
                loc = err.get("loc", ["unknown"])
                field = str(loc[-1]) if loc else "unknown"
                msg = cls.translate_pydantic_error(err, target_lang=target_lang)
                translated.append({field: msg})
        except Exception:
            translated.append({"error": str(validation_exception)})
        return translated

    @classmethod
    def t(cls, key: str, lang: Optional[str] = None, request: Any = None, default: Optional[str] = None) -> str:
        """Translates a key with fallback to default string or key itself."""
        target_lang = lang or cls.lang(request)
        dic = cls.get_dict(target_lang)
        val = dic.get(key)
        if val:
            return val
        return default if default is not None else key

