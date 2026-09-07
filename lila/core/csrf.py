import secrets
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import SECRET_KEY
from lila.core.request import Request
from lila.core.logger import Logger

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="csrf")

CSRF_COOKIE_NAME = "_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_FIELD_NAME = "csrf"
CSRF_MAX_AGE = 3600


class CSRF:
    """
    English: Provides CSRF token generation and verification for Lila Framework.
    Tokens are random values stored raw in the request state and signed via itsdangerous in a cookie.

    Español: Provee generacion y verificacion de tokens CSRF para Lila Framework.
    Los tokens son valores aleatorios almacenados sin firmar en el estado del request
    y firmados con itsdangerous en una cookie.
    """

    @staticmethod
    def generate(request: Request) -> str:
        """
        English: Generates or retrieves the current CSRF token for this request.
        The raw token is cached in request.state._csrf_token to avoid regeneration.

        Español: Genera o recupera el token CSRF actual para este request.
        El token raw se cachea en request.state._csrf_token para evitar regeneracion.
        """
        if hasattr(request.state, "_csrf_token") and request.state._csrf_token:
            return request.state._csrf_token

        existing_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if existing_cookie:
            raw = CSRF._unsign(existing_cookie)
            if raw:
                request.state._csrf_token = raw
                return raw

        token = secrets.token_urlsafe(32)
        request.state._csrf_token = token
        return token

    @staticmethod
    def sign(token: str) -> str:
        """
        English: Signs a raw CSRF token using itsdangerous for cookie storage.

        Español: Firma un token CSRF raw usando itsdangerous para almacenarlo en cookie.
        """
        return _serializer.dumps(token)

    @staticmethod
    def _unsign(signed_token: str) -> str | None:
        """
        English: Unsigns a cookie value and returns the raw token, or None if invalid/expired.

        Español: Desencripta el valor de la cookie y retorna el token raw, o None si es invalido/expirado.
        """
        try:
            return _serializer.loads(signed_token, max_age=CSRF_MAX_AGE)
        except SignatureExpired:
            return None
        except BadSignature:
            return None
        except Exception:
            return None

    @staticmethod
    def verify(request: Request) -> bool:
        """
        English: Verifies the CSRF token from the request against the signed cookie.
        The token is read from the X-CSRF-Token header first, then from the request body field 'csrf'.
        Returns True if valid, False otherwise.

        Español: Verifica el token CSRF del request contra la cookie firmada.
        El token se lee primero del header X-CSRF-Token, luego del campo 'csrf' del body.
        Retorna True si es valido, False en caso contrario.
        """
        signed_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if not signed_cookie:
            Logger.warning("CSRF verification failed: cookie not found.")
            return False

        expected_token = CSRF._unsign(signed_cookie)
        if not expected_token:
            return False

        submitted_token = request.headers.get(CSRF_HEADER_NAME)

        if not submitted_token:
            body_data = getattr(request.state, "data", None)
            if body_data:
                if hasattr(body_data, "dict"):
                    submitted_token = body_data.dict().get(CSRF_FIELD_NAME)
                elif isinstance(body_data, dict):
                    submitted_token = body_data.get(CSRF_FIELD_NAME)

        if not submitted_token:
            Logger.warning("CSRF verification failed: token not found in header or body.")
            return False

        if not secrets.compare_digest(str(submitted_token), str(expected_token)):
            Logger.warning("CSRF verification failed: token mismatch.")
            return False

        return True

    @staticmethod
    def set_cookie(response, token: str) -> None:
        """
        English: Sets the signed CSRF token as an HttpOnly cookie on the response.

        Español: Establece el token CSRF firmado como cookie HttpOnly en la respuesta.
        """
        signed = CSRF.sign(token)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=signed,
            max_age=CSRF_MAX_AGE,
            expires=CSRF_MAX_AGE,
            httponly=True,
            samesite="strict",
            path="/",
        )
