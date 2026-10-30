"""Lila Framework v2.0.x CSRF Protection.

Signed double-submit cookies via itsdangerous. The token comes from:
1. ``X-CSRF-Token`` header (``Http()`` / fetch clients),
2. the parsed JSON or form body (``_csrf`` / ``csrf`` fields),
3. ``request.state.raw_data`` when the routing layer already parsed it.

Query-string tokens are intentionally NOT accepted (they leak through logs,
Referer headers and browser history).
"""

import secrets
from typing import Optional, Any

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from lila.core.config import ENV_CONFIG, get_secret_key
from lila.core.request import Request

CSRF_COOKIE_NAME = "_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_MAX_AGE = 7200
CSRF_FIELD_NAMES = ("_csrf", "csrf", "csrf_token")


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_secret_key(), salt="lila-csrf-salt")


def _token_from_mapping(data: Any) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, dict):
        for field in CSRF_FIELD_NAMES:
            value = data.get(field)
            if value:
                return str(value)
        return None
    for field in CSRF_FIELD_NAMES:
        value = getattr(data, field, None)
        if value:
            return str(value)
    return None


class CSRF:
    @staticmethod
    def generate(request: Request) -> str:
        """Generates or retrieves the current CSRF token from cookie/request state."""
        existing = getattr(request.state, "csrf_token", None)
        if existing:
            return existing

        cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
        if cookie_val:
            raw = CSRF.unsign(cookie_val)
            if raw:
                request.state.csrf_token = raw
                return raw

        token = secrets.token_urlsafe(32)
        request.state.csrf_token = token
        return token

    @staticmethod
    def sign(token: str) -> str:
        return _get_serializer().dumps(token)

    @staticmethod
    def unsign(signed_token: str) -> Optional[str]:
        try:
            return _get_serializer().loads(signed_token, max_age=CSRF_MAX_AGE)
        except (SignatureExpired, BadSignature, Exception):
            return None

    @staticmethod
    def _expected(request: Request) -> Optional[str]:
        cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
        if not cookie_val:
            return None
        return CSRF.unsign(cookie_val)

    @staticmethod
    def verify(request: Request, submitted_token: Optional[str] = None) -> bool:
        """Synchronous verification (header / already-parsed body).

        Use :meth:`verify_async` when the form body has not been parsed yet.
        """
        expected = CSRF._expected(request)
        if not expected:
            return False

        token = submitted_token or request.headers.get(CSRF_HEADER_NAME)
        if not token:
            token = _token_from_mapping(getattr(request.state, "raw_data", None))
        if not token:
            token = _token_from_mapping(getattr(request.state, "data", None))

        if not token:
            return False
        return secrets.compare_digest(str(expected), str(token))

    @staticmethod
    async def verify_async(request: Request, submitted_token: Optional[str] = None) -> bool:
        """Verifies a CSRF token, parsing JSON/form bodies when needed."""
        expected = CSRF._expected(request)
        if not expected:
            return False

        token = submitted_token or request.headers.get(CSRF_HEADER_NAME)
        if token:
            return secrets.compare_digest(str(expected), str(token))

        token = _token_from_mapping(getattr(request.state, "raw_data", None))
        if token:
            return secrets.compare_digest(str(expected), str(token))

        content_type = request.headers.get("content-type", "")
        try:
            if "application/json" in content_type:
                data = await request.json()
                token = _token_from_mapping(data)
            elif (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                form = await request.form()
                token = _token_from_mapping(dict(form))
        except Exception:
            token = None

        if not token:
            token = _token_from_mapping(getattr(request.state, "data", None))
        if not token:
            return False
        return secrets.compare_digest(str(expected), str(token))
