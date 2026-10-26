"""Lila Framework v2.0.0 CSRF Protection.
Signed double-submit cookies via itsdangerous.
"""

import secrets
from typing import Optional
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from lila.core.config import ENV_CONFIG
from lila.core.request import Request

CSRF_COOKIE_NAME = "_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_MAX_AGE = 7200


def _get_serializer() -> URLSafeTimedSerializer:
    secret = str(ENV_CONFIG.get("SECRET_KEY", "lila-fallback-secret-key-change-me-v2"))
    return URLSafeTimedSerializer(secret, salt="lila-csrf-salt")


class CSRF:
    @staticmethod
    def generate(request: Request) -> str:
        """Generates or retrieves current CSRF token from cookie or request state."""
        if hasattr(request.state, "_csrf_token") and request.state._csrf_token:
            return request.state._csrf_token

        cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
        if cookie_val:
            raw = CSRF.unsign(cookie_val)
            if raw:
                request.state._csrf_token = raw
                return raw

        token = secrets.token_urlsafe(32)
        request.state._csrf_token = token
        return token

    @staticmethod
    def sign(token: str) -> str:
        """Signs raw token for secure cookie storage."""
        return _get_serializer().dumps(token)

    @staticmethod
    def unsign(signed_token: str) -> Optional[str]:
        """Validates and unpacks signed cookie token."""
        try:
            return _get_serializer().loads(signed_token, max_age=CSRF_MAX_AGE)
        except (SignatureExpired, BadSignature, Exception):
            return None

    @staticmethod
    def verify(request: Request, submitted_token: Optional[str] = None) -> bool:
        """Verifies submitted token against signed cookie."""
        cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
        if not cookie_val:
            return False

        expected = CSRF.unsign(cookie_val)
        if not expected:
            return False

        if not submitted_token:
            # Check header
            submitted_token = request.headers.get(CSRF_HEADER_NAME)

        if not submitted_token:
            # Check query param
            submitted_token = request.query_params.get("_csrf") or request.query_params.get("csrf")

        if not submitted_token:
            # Check state data if present
            data = getattr(request.state, "data", None)
            if isinstance(data, dict):
                submitted_token = data.get("_csrf") or data.get("csrf")
            elif hasattr(data, "__dict__"):
                submitted_token = getattr(data, "_csrf", None) or getattr(data, "csrf", None)

        if not submitted_token:
            return False

        return secrets.compare_digest(str(expected), str(submitted_token))
