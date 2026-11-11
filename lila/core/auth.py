"""Lila Framework v2.0.x Authentication & Password Hashing.

JWT helpers and Argon2 password hashing with a native scrypt fallback.
Async helpers offload the CPU-bound hash to a worker thread so the event loop
is never blocked for ~100 ms per login.
"""

import asyncio
import hashlib
import secrets
import base64
from datetime import datetime, timedelta, timezone
from typing import Union, Any, Optional

import jwt

from lila.core.config import ENV_CONFIG, get_secret_key
from lila.core.request import Request
from lila.core.responses import JSONResponse

try:
    from argon2 import PasswordHasher as _Argon2Hasher
    from argon2.exceptions import VerifyMismatchError, VerificationError
    HAS_ARGON2 = True
    # OWASP-recommended Argon2id parameters (19 MiB) instead of 64 MiB.
    _argon2 = _Argon2Hasher(time_cost=2, memory_cost=19456, parallelism=1)
except ImportError:  # pragma: no cover - optional dependency
    HAS_ARGON2 = False
    _argon2 = None

try:
    import argon2 as _argon2_module
except ImportError:  # pragma: no cover
    _argon2_module = None


def _get_secret() -> str:
    return get_secret_key()


class PasswordHasher:
    """Argon2 password hasher with automatic native scrypt fallback."""

    @classmethod
    def hash(cls, password: str) -> str:
        if not password:
            raise ValueError("Password cannot be empty")

        if HAS_ARGON2 and _argon2 is not None:
            return _argon2.hash(password)

        salt = secrets.token_bytes(16)
        derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(derived).decode("ascii")
        return f"$scrypt$ln=14,r=8,p=1${salt_b64}${hash_b64}"

    @classmethod
    async def hash_async(cls, password: str) -> str:
        """Non-blocking hash for async routes."""
        return await asyncio.to_thread(cls.hash, password)

    @classmethod
    def verify(cls, hashed: str, password: str) -> bool:
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
                salt = base64.b64decode(parts[3])
                expected = base64.b64decode(parts[4])
                derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
                return secrets.compare_digest(derived, expected)
            except Exception:
                return False

        # Legacy salted SHA-256 compatibility (salt$sha256)
        if "$" in hashed:
            try:
                salt, sha = hashed.split("$", 1)
                candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
                return secrets.compare_digest(candidate, sha)
            except Exception:
                return False

        return False

    @classmethod
    async def verify_async(cls, hashed: str, password: str) -> bool:
        """Non-blocking verification for async routes."""
        return await asyncio.to_thread(cls.verify, hashed, password)

    @classmethod
    def needs_rehash(cls, hashed: str) -> bool:
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
        now = datetime.now(timezone.utc)
        data.setdefault("iat", now)
        data["exp"] = now + timedelta(minutes=minutes)
        return jwt.encode(data, sec, algorithm="HS256")

    # ── Access + refresh token pairs ────────────────────────────────────────
    _REFRESH_SCHEMA = """
    CREATE TABLE IF NOT EXISTS jwt_refresh (
        jti TEXT PRIMARY KEY,
        family TEXT NOT NULL,
        subject TEXT,
        expires_at REAL NOT NULL,
        used_at REAL,
        revoked INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS ix_jwt_refresh_family ON jwt_refresh (family);
    """

    @classmethod
    def _store(cls):
        from lila.core import system_db

        return system_db.connect("lila_system", cls._REFRESH_SCHEMA)

    @classmethod
    def issue_pair(cls, payload: dict, access_minutes: int = 15, refresh_days: int = 30,
                   family: Optional[str] = None) -> dict:
        """Short-lived access token + long-lived refresh token (rotated on use).

        ``{"access_token", "refresh_token", "token_type": "bearer", "expires_in"}``.
        Refresh state lives in ``app/data/lila_system.db`` (shared by workers,
        survives restarts); only the token id is stored, never the token.
        """
        import time as _time

        data = {k: v for k, v in dict(payload).items() if k not in ("exp", "iat", "jti", "typ", "fam")}
        access = JWT.encode({**data, "typ": "access"}, minutes=access_minutes)
        jti = secrets.token_urlsafe(16)
        fam = family or secrets.token_urlsafe(12)
        refresh = JWT.encode({**data, "typ": "refresh", "jti": jti, "fam": fam}, minutes=refresh_days * 1440)
        subject = str(data.get("user_id", data.get("sub", "")))
        cls._store().execute(
            "INSERT INTO jwt_refresh (jti, family, subject, expires_at) VALUES (?, ?, ?, ?)",
            (jti, fam, subject, _time.time() + refresh_days * 86400),
        )
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer",
                "expires_in": access_minutes * 60}

    @classmethod
    def refresh(cls, refresh_token: str, access_minutes: int = 15, refresh_days: int = 30) -> Optional[dict]:
        """Exchanges a refresh token for a new pair. A refresh token works once:
        re-using an old one (stolen token) revokes the whole family."""
        import time as _time

        data = JWT.decode(refresh_token)
        if not data or data.get("typ") != "refresh" or not data.get("jti"):
            return None
        store = cls._store()
        row = store.execute("SELECT family, used_at, revoked, expires_at FROM jwt_refresh WHERE jti = ?",
                            (data["jti"],)).fetchone()
        if row is None or row["revoked"] or row["expires_at"] < _time.time():
            return None
        if row["used_at"] is not None:
            store.execute("UPDATE jwt_refresh SET revoked = 1 WHERE family = ?", (row["family"],))
            return None
        cur = store.execute("UPDATE jwt_refresh SET used_at = ? WHERE jti = ? AND used_at IS NULL",
                            (_time.time(), data["jti"]))
        if cur.rowcount != 1:  # lost a race with a concurrent refresh
            return None
        claims = {k: v for k, v in data.items() if k not in ("exp", "iat", "jti", "typ", "fam")}
        return cls.issue_pair(claims, access_minutes, refresh_days, family=row["family"])

    @classmethod
    async def refresh_async(cls, refresh_token: str, access_minutes: int = 15, refresh_days: int = 30) -> Optional[dict]:
        return await asyncio.to_thread(cls.refresh, refresh_token, access_minutes, refresh_days)

    @classmethod
    def revoke(cls, refresh_token: str) -> bool:
        """Logout: revokes the token's family (every token issued from that login)."""
        data = JWT.decode(refresh_token)
        if not data or data.get("typ") != "refresh":
            return False
        cur = cls._store().execute("UPDATE jwt_refresh SET revoked = 1 WHERE family = ?", (data.get("fam"),))
        return cur.rowcount > 0

    @classmethod
    def revoke_user(cls, subject: Any) -> int:
        """Revokes every refresh token of a user (password change, "log out everywhere")."""
        return cls._store().execute("UPDATE jwt_refresh SET revoked = 1 WHERE subject = ?", (str(subject),)).rowcount

    @classmethod
    def prune(cls) -> int:
        import time as _time

        return cls._store().execute("DELETE FROM jwt_refresh WHERE expires_at < ?", (_time.time(),)).rowcount

    @staticmethod
    def decode(token_str: str, secret: Optional[str] = None) -> Optional[dict]:
        sec = secret or _get_secret()
        if not token_str:
            return None
        if " " in token_str:
            token_str = token_str.strip().split(" ", 1)[1]
        try:
            return jwt.decode(token_str, sec, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
            return None


def generate_token_value(hex_length: int = 16) -> str:
    return hashlib.sha256(secrets.token_hex(hex_length).encode()).hexdigest()


def generate_token(name: str, value: Any = None, minutes: int = 1440) -> str:
    options = {name: value if value is not None else generate_token_value()}
    return JWT.encode(options, minutes=minutes)


def get_token(token_str: str) -> Union[dict, JSONResponse]:
    sec = _get_secret()
    try:
        if " " in token_str:
            token_str = token_str.strip().split(" ", 1)[1]
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
