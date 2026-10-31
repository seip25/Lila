"""Lila Framework v2.0.2 Lightweight Translation Engine.
Fast, in-memory Pydantic v2 validation error translation (es, en, pt, zh)
with zero disk I/O and zero session overhead per request.
"""

from typing import Optional, Any
from jinja2 import Undefined
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
    "zh": {
        "missing": "此字段为必填项。",
        "string_type": "请输入有效的文本。",
        "string_too_short": "至少需要 {min_length} 个字符。",
        "string_too_long": "不能超过 {max_length} 个字符。",
        "string_pattern_mismatch": "格式不符合要求。",
        "int_parsing": "请输入有效的整数。",
        "float_parsing": "请输入有效的数字。",
        "bool_parsing": "请输入 true 或 false。",
        "greater_than": "数值必须大于 {gt}。",
        "greater_than_equal": "数值必须大于或等于 {ge}。",
        "less_than": "数值必须小于 {lt}。",
        "less_than_equal": "数值必须小于或等于 {le}。",
        "value_error": "值无效。",
        "value_error.email": "请输入有效的电子邮箱地址。",
        "email": "请输入有效的电子邮箱地址。",
        "url_parsing": "请输入有效的 URL。",
        "uuid_parsing": "请输入有效的 UUID。",
        "date_parsing": "请输入有效日期 (YYYY-MM-DD)。",
        "datetime_parsing": "请输入有效的日期时间。",
        "list_type": "请输入有效的列表。",
        "dict_type": "请输入有效的对象。",
        "literal_error": "请选择允许的值。",
        "too_short": "至少需要 {min_length} 项。",
        "too_long": "不能超过 {max_length} 项。",
    },
}


class SafeTranslationDict(dict):
    """Translation dictionary that behaves like Jinja's ``Undefined`` for misses.

    Returning a real ``Undefined`` (instead of ``""``) is what makes
    ``{{ translate['missing'] | default('Fallback') }}`` work; previously the
    default filter never fired and labels rendered blank.
    """

    def __init__(self, data: Optional[dict] = None, lang: str = "en") -> None:
        super().__init__(data or {})
        self.lang = lang

    def __getitem__(self, key: str) -> Any:
        val = super().get(key)
        if val is None or val == "":
            val = super().get(str(key).lower())
        if val is not None and val != "":
            return val
        return Undefined(name=key)

    def __missing__(self, key: str) -> Any:
        return Undefined(name=key)

    def get(self, key: str, default: Any = None) -> Any:
        val = super().get(key)
        if val is None or val == "":
            val = super().get(str(key).lower())
        if val is not None and val != "":
            return val
        return default if default is not None else ""


_LOCALES_CACHE: dict[str, SafeTranslationDict] = {}


class Translate:
    """Fast, zero-overhead translator specialized in Pydantic v2 validation errors and UI locales."""

    BUILTIN_LOCALES = {
        "en": {
            "login": "Welcome Back",
            "sign_in": "Sign In",
            "sign_in_desc": "Sign in to your account",
            "register": "Create Account",
            "create_account": "Create account",
            "create account": "Create account",
            "register_desc": "Get started in seconds",
            "email": "Email Address",
            "password": "Password",
            "confirm_password": "Confirm Password",
            "forgot_password": "Forgot Password?",
            "forgot your password": "Forgot your password?",
            "forgot_instruction": "Enter your email address and we will send you a link to reset your password.",
            "recover_password": "Recover password",
            "recover password": "Recover password",
            "reset_password": "Reset Password",
            "logout": "Log Out",
            "dashboard": "Dashboard",
            "profile": "Profile",
            "welcome": "Welcome",
            "save": "Save",
            "cancel": "Cancel",
            "submit": "Submit",
            "send": "Send",
            "delete": "Delete",
            "edit": "Edit",
            "create": "Create",
            "search": "Search",
            "back": "Go Back",
            "go_back_home": "Go Back Home",
            "not_found": "Page Not Found",
            "page_not_found_desc": "The page you are looking for might have been moved, deleted, or does not exist.",
            "name": "Name",
            "full_name": "Full Name",
            "home": "Home",
            "current": "Current",
            "new": "New",
            "new_password": "New password",
            "optional": "Optional",
            "is_required": "is required",
            "is required": "is required",
            "delete_account": "Delete Account",
            "delete account": "Delete Account",
            "danger_zone": "Danger Zone",
            "passwords_not_match": "Passwords do not match",
            "passwords not match": "Passwords do not match",
            "invalid_or_expired_token": "Invalid or expired token",
            "invalid or expired token": "Invalid or expired token",
            "request_new_password_reset_link": "Request a new password reset link",
            "request new password reset link": "Request a new password reset link",
            "your_password_reset_link_is_invalid_or_has_expired": "Your password reset link is invalid or has expired.",
            "your password reset link is invalid or has expired.": "Your password reset link is invalid or has expired.",
            "once_you_delete_your_account_there_is_no_going_back": "Once you delete your account, there is no going back.",
            "or_with_email": "Or with email",
            "dont_have_account": "Don't have an account?",
            "already_have_account": "Already have an account?",
            "continue_with": "Continue with",
            "sign_up_with": "Sign up with",
            "account_created": "Account Created",
            "authenticated_success": "Authenticated successfully!",
            "invalid_credentials": "Invalid credentials.",
            "registration_failed": "Registration failed.",
            "connection_failed": "Connection failed",
            "menu": "Menu",
            "error": "Error",
            "success": "Success",
            "notice": "Notice",
            "manage_profile_desc": "Manage your account details and security settings.",
            "admin": "Admin",
            "system": "System",
            "sign_out": "Sign Out",
        },
        "es": {
            "login": "Bienvenido de nuevo",
            "sign_in": "Iniciar Sesión",
            "sign_in_desc": "Inicia sesión en tu cuenta",
            "register": "Crear Cuenta",
            "create_account": "Crear cuenta",
            "create account": "Crear cuenta",
            "register_desc": "Comienza en segundos",
            "email": "Correo Electrónico",
            "password": "Contraseña",
            "confirm_password": "Confirmar Contraseña",
            "forgot_password": "¿Olvidaste tu contraseña?",
            "forgot your password": "¿Olvidaste tu contraseña?",
            "forgot_instruction": "Ingresá tu correo y te enviaremos un enlace para restablecer tu contraseña.",
            "recover_password": "Recuperar contraseña",
            "recover password": "Recuperar contraseña",
            "reset_password": "Restablecer Contraseña",
            "logout": "Cerrar Sesión",
            "dashboard": "Panel de Control",
            "profile": "Perfil",
            "welcome": "Bienvenido",
            "save": "Guardar",
            "cancel": "Cancelar",
            "submit": "Enviar",
            "send": "Enviar",
            "delete": "Eliminar",
            "edit": "Editar",
            "create": "Crear",
            "search": "Buscar",
            "back": "Volver",
            "go_back_home": "Volver al Inicio",
            "not_found": "Página no encontrada",
            "page_not_found_desc": "La página que buscas pudo haber sido movida, eliminada o no existir.",
            "name": "Nombre",
            "full_name": "Nombre Completo",
            "home": "Inicio",
            "current": "Actual",
            "new": "Nueva",
            "new_password": "Nueva contraseña",
            "optional": "Opcional",
            "is_required": "es requerido",
            "is required": "es requerido",
            "delete_account": "Eliminar Cuenta",
            "delete account": "Eliminar Cuenta",
            "danger_zone": "Zona de Peligro",
            "passwords_not_match": "Las contraseñas no coinciden",
            "passwords not match": "Las contraseñas no coinciden",
            "invalid_or_expired_token": "Token inválido o expirado",
            "invalid or expired token": "Token inválido o expirado",
            "request_new_password_reset_link": "Solicitar un nuevo enlace de restablecimiento",
            "request new password reset link": "Solicitar un nuevo enlace de restablecimiento",
            "your_password_reset_link_is_invalid_or_has_expired": "Tu enlace de restablecimiento es inválido o expiró.",
            "your password reset link is invalid or has expired.": "Tu enlace de restablecimiento es inválido o expiró.",
            "once_you_delete_your_account_there_is_no_going_back": "Una vez que elimines tu cuenta, no hay vuelta atrás.",
            "or_with_email": "O con correo electrónico",
            "dont_have_account": "¿No tienes una cuenta?",
            "already_have_account": "¿Ya tienes una cuenta?",
            "continue_with": "Continuar con",
            "sign_up_with": "Registrarse con",
            "account_created": "Cuenta Creada",
            "authenticated_success": "¡Autenticado con éxito!",
            "invalid_credentials": "Credenciales inválidas.",
            "registration_failed": "El registro falló.",
            "connection_failed": "Error de conexión",
            "menu": "Menú",
            "error": "Error",
            "success": "Éxito",
            "notice": "Aviso",
            "manage_profile_desc": "Administra los detalles de tu cuenta y configuración de seguridad.",
            "admin": "Administración",
            "system": "Sistema",
            "sign_out": "Cerrar Sesión",
        },
        "pt": {
            "login": "Bem-vindo de volta",
            "sign_in": "Entrar",
            "sign_in_desc": "Entre na sua conta",
            "register": "Criar Conta",
            "create_account": "Criar conta",
            "create account": "Criar conta",
            "register_desc": "Comece em segundos",
            "email": "Endereço de E-mail",
            "password": "Senha",
            "confirm_password": "Confirmar Senha",
            "forgot_password": "Esqueceu sua senha?",
            "forgot your password": "Esqueceu sua senha?",
            "forgot_instruction": "Digite seu e-mail e enviaremos um link para redefinir sua senha.",
            "recover_password": "Recuperar senha",
            "recover password": "Recuperar senha",
            "reset_password": "Redefinir Senha",
            "logout": "Sair",
            "dashboard": "Painel de Controle",
            "profile": "Perfil",
            "welcome": "Bem-vindo",
            "save": "Salvar",
            "cancel": "Cancelar",
            "submit": "Enviar",
            "send": "Enviar",
            "delete": "Excluir",
            "edit": "Editar",
            "create": "Criar",
            "search": "Pesquisar",
            "back": "Voltar",
            "go_back_home": "Voltar ao Início",
            "not_found": "Página não encontrada",
            "page_not_found_desc": "A página que você procura pode ter sido movida, excluída ou não existir.",
            "name": "Nome",
            "full_name": "Nome Completo",
            "home": "Início",
            "current": "Atual",
            "new": "Nova",
            "new_password": "Nova senha",
            "optional": "Opcional",
            "is_required": "é obrigatório",
            "is required": "é obrigatório",
            "delete_account": "Excluir Conta",
            "delete account": "Excluir Conta",
            "danger_zone": "Zona de Perigo",
            "passwords_not_match": "As senhas não coincidem",
            "passwords not match": "As senhas não coincidem",
            "invalid_or_expired_token": "Token inválido ou expirado",
            "invalid or expired token": "Token inválido ou expirado",
            "request_new_password_reset_link": "Solicitar novo link de redefinição de senha",
            "request new password reset link": "Solicitar novo link de redefinição de senha",
            "your_password_reset_link_is_invalid_or_has_expired": "Seu link de redefinição de senha é inválido ou expirou.",
            "your password reset link is invalid or has expired.": "Seu link de redefinição de senha é inválido ou expirou.",
            "once_you_delete_your_account_there_is_no_going_back": "Depois de excluir sua conta, não há volta.",
            "or_with_email": "Ou com e-mail",
            "dont_have_account": "Não tem uma conta?",
            "already_have_account": "Já tem uma conta?",
            "continue_with": "Continuar com",
            "sign_up_with": "Cadastre-se com",
            "account_created": "Conta Criada",
            "authenticated_success": "Autenticado com sucesso!",
            "invalid_credentials": "Credenciais inválidas.",
            "registration_failed": "Falha no cadastro.",
            "connection_failed": "Falha na conexão",
            "menu": "Menu",
            "error": "Erro",
            "success": "Sucesso",
            "notice": "Aviso",
            "manage_profile_desc": "Gerencie os detalhes da sua conta e configurações de segurança.",
            "admin": "Administração",
            "system": "Sistema",
            "sign_out": "Sair",
        },
        "zh": {
            "login": "欢迎回来",
            "sign_in": "登录",
            "sign_in_desc": "登录您的账户",
            "register": "创建账户",
            "create_account": "创建账户",
            "create account": "创建账户",
            "register_desc": "只需几秒即可开始",
            "email": "电子邮箱",
            "password": "密码",
            "confirm_password": "确认密码",
            "forgot_password": "忘记密码？",
            "forgot your password": "忘记密码？",
            "forgot_instruction": "请输入您的电子邮箱，我们会发送重置密码的链接。",
            "recover_password": "找回密码",
            "recover password": "找回密码",
            "reset_password": "重置密码",
            "logout": "退出登录",
            "dashboard": "控制台",
            "profile": "个人资料",
            "welcome": "欢迎",
            "save": "保存",
            "cancel": "取消",
            "submit": "提交",
            "send": "发送",
            "delete": "删除",
            "edit": "编辑",
            "create": "创建",
            "search": "搜索",
            "back": "返回",
            "go_back_home": "返回首页",
            "not_found": "页面未找到",
            "page_not_found_desc": "您查找的页面可能已被移动、删除或不存在。",
            "name": "姓名",
            "full_name": "全名",
            "home": "首页",
            "current": "当前",
            "new": "新",
            "new_password": "新密码",
            "optional": "可选",
            "is_required": "为必填项",
            "is required": "为必填项",
            "delete_account": "删除账户",
            "delete account": "删除账户",
            "danger_zone": "危险操作",
            "passwords_not_match": "两次输入的密码不一致",
            "passwords not match": "两次输入的密码不一致",
            "invalid_or_expired_token": "链接无效或已过期",
            "invalid or expired token": "链接无效或已过期",
            "request_new_password_reset_link": "申请新的重置链接",
            "request new password reset link": "申请新的重置链接",
            "your_password_reset_link_is_invalid_or_has_expired": "重置链接无效或已过期。",
            "your password reset link is invalid or has expired.": "重置链接无效或已过期。",
            "once_you_delete_your_account_there_is_no_going_back": "删除账户后无法恢复。",
            "or_with_email": "或通过电子邮箱",
            "dont_have_account": "还没有账户？",
            "already_have_account": "已经有账户了？",
            "continue_with": "继续使用",
            "sign_up_with": "注册使用",
            "account_created": "账户已创建",
            "authenticated_success": "认证成功！",
            "invalid_credentials": "凭据无效。",
            "registration_failed": "注册失败。",
            "connection_failed": "连接失败",
            "menu": "菜单",
            "error": "错误",
            "success": "成功",
            "notice": "提示",
            "manage_profile_desc": "管理您的账户详情和安全设置。",
            "admin": "管理",
            "system": "系统",
            "sign_out": "退出登录",
        },
    }

    @classmethod
    def lang(cls, request: Any = None, lang_default: Optional[str] = None) -> str:
        """Determines requested language with fast O(1) in-memory checks."""
        force = ENV_CONFIG.get_bool("LANG_FORCE", False)
        default_lang = (lang_default or ENV_CONFIG.get("LANG_DEFAULT", "en"))[:2].lower()

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

            if force:
                return default_lang

            # 3. Header Accept-Language (honours q-values and region variants)
            try:
                header = request.headers.get("accept-language")
                if header:
                    best = None
                    best_q = -1.0
                    for part in header.split(","):
                        bits = part.strip().split(";")
                        code = bits[0].strip()[:2].lower()
                        if not code or not code.isalpha():
                            continue
                        quality = 1.0
                        for bit in bits[1:]:
                            bit = bit.strip()
                            if bit.startswith("q="):
                                try:
                                    quality = float(bit[2:])
                                except ValueError:
                                    quality = 0.0
                        if quality > best_q:
                            best_q = quality
                            best = code
                    if best:
                        return best
            except Exception:
                pass

        # 4. Fallback from environment
        return default_lang

    @classmethod
    def set_lang(cls, request: Any, response: Any, lang: str, max_age: int = 31536000) -> bool:
        """Persists the language choice in a cookie (v1/v2 docs helper)."""
        try:
            code = str(lang or "en")[:2].lower()
            response.set_cookie(
                "lang",
                code,
                max_age=max_age,
                httponly=False,
                samesite="lax",
                secure=str(ENV_CONFIG.get("APP_URL", "")).lower().startswith("https://"),
            )
            return True
        except Exception:
            return False

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
    def t(
        cls,
        key: str,
        lang: Optional[str] = None,
        request: Any = None,
        default: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> str:
        """Translates a key with fallback to default string or the key itself."""
        target_lang = lang or cls.lang(request)
        dic = cls.get_dict(target_lang)
        val = dic.get(key)
        if val:
            return val
        if file_name:
            # v1 compatibility: older projects grouped keys by file; look for
            # ``file_name.key`` and ``key`` in the same flat dictionary.
            val = dic.get(f"{file_name}.{key}")
            if val:
                return val
        return default if default is not None else key
