"""Lila Framework v2.0.0 Authentication & Password Hashing.
Provides JWT helpers and Argon2 password hashing with native scrypt fallback.
"""

import hashlib
import secrets
import base64
from datetime import datetime, timedelta, timezone
from typing import Union, Any, Optional
import jwt

from lila.core.config import ENV_CONFIG
from lila.core.request import Request
from lila.core.responses import JSONResponse

try:
    from argon2 import PasswordHasher as _Argon2Hasher
    from argon2.exceptions import VerifyMismatchError, VerificationError
    HAS_ARGON2 = True
    _argon2 = _Argon2Hasher(time_cost=2, memory_cost=65536, parallelism=1)
except ImportError:
    HAS_ARGON2 = False
    _argon2 = None


def _get_secret() -> str:
    return str(ENV_CONFIG.get("SECRET_KEY", "lila-auth-secret-key-change-me"))


class PasswordHasher:
    """Argon2 password hasher with automatic native scrypt fallback."""

    @classmethod
    def hash(cls, password: str) -> str:
        """Hashes password with Argon2 (or PBKDF2/scrypt if argon2 is unavailable)."""
        if not password:
            raise ValueError("Password cannot be empty")

        if HAS_ARGON2 and _argon2 is not None:
            return _argon2.hash(password)

        # Secure native scrypt fallback
        salt = secrets.token_bytes(16)
        derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(derived).decode("ascii")
        return f"$scrypt$ln=14,r=8,p=1${salt_b64}${hash_b64}"

    @classmethod
    def verify(cls, hashed: str, password: str) -> bool:
        """Verifies password against stored hash."""
        if not hashed or not password:
            return False

        # Argon2 hash ($argon2id$, $argon2i$, $argon2d$)
        if hashed.startswith("$argon2"):
            if HAS_ARGON2 and _argon2 is not None:
                try:
                    return _argon2.verify(hashed, password)
                except (VerifyMismatchError, VerificationError, Exception):
                    return False
            return False

        # Scrypt hash
        if hashed.startswith("$scrypt$"):
            try:
                parts = hashed.split("$")
                # parts: ['', 'scrypt', 'ln=14,r=8,p=1', salt_b64, hash_b64]
                salt = base64.b64decode(parts[3])
                expected = base64.b64decode(parts[4])
                derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
                return secrets.compare_digest(derived, expected)
            except Exception:
                return False

        # Fallback SHA-256 for legacy compatibility (salt$sha256)
        if "$" in hashed:
            salt, sha = hashed.split("$", 1)
            candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
            return secrets.compare_digest(candidate, sha)

        return False

    @classmethod
    def needs_rehash(cls, hashed: str) -> bool:
        """Checks if hash needs rehash to modern Argon2 format."""
        if HAS_ARGON2 and _argon2 is not None:
            if not hashed.startswith("$argon2"):
                return True
            try:
                return _argon2.check_needs_rehash(hashed)
            except Exception:
                return True
        return False


class JWT:
    """JWT Token encoder/decoder helpers."""

    @staticmethod
    def encode(payload: dict, minutes: int = 1440, secret: Optional[str] = None) -> str:
        sec = secret or _get_secret()
        data = dict(payload)
        data["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return jwt.encode(data, sec, algorithm="HS256")

    @staticmethod
    def decode(token_str: str, secret: Optional[str] = None) -> Optional[dict]:
        sec = secret or _get_secret()
        if " " in token_str:
            token_str = token_str.strip().split(" ")[1]
        try:
            return jwt.decode(token_str, sec, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
            return None


def generate_token_value(hex_length: int = 16) -> str:
    return hashlib.sha256(secrets.token_hex(hex_length).encode()).hexdigest()


def generate_token(name: str, value: Any = None, minutes: int = 1440) -> str:
    options = {
        name: value if value is not None else generate_token_value(),
    }
    return JWT.encode(options, minutes=minutes)


def get_token(token_str: str) -> Union[dict, JSONResponse]:
    sec = _get_secret()
    try:
        if " " in token_str:
            token_str = token_str.strip().split(" ")[1]
        return jwt.decode(token_str, sec, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return JSONResponse({"session": False, "message": "Token has expired"}, status_code=401)
    except jwt.InvalidTokenError:
        return JSONResponse({"session": False, "message": "Invalid token"}, status_code=401)


def get_user_id_by_token(request: Request, key: str = "user_id") -> Any:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse({"session": False, "message": "Missing Authorization header"}, status_code=401)

    token_data = get_token(auth_header)
    if isinstance(token_data, JSONResponse):
        return token_data

    user_id = token_data.get(key)
    if user_id is None:
        return JSONResponse({"session": False, "message": "User ID not found in token"}, status_code=401)
    return user_id
