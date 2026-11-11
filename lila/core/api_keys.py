"""Per-user API keys for scripts, mobile apps and integrations.

    # app/models/api_keys.py  (so `lila migrate` creates the table)
    from lila.core.api_keys import ApiKey  # noqa: F401

    from lila.core.api_keys import ApiKeys

    token, key = await ApiKeys.create_async(user_id=7, name="CI", scopes=["posts.read"], expires_days=90)
    # show `token` ONCE (lila_xxxxxxxx_...); only its SHA-256 is stored

    @router.get("/api/posts", api_key=True)              # any valid key
    @router.post("/api/posts", api_key=["posts.write"])  # key must have these scopes
    async def ...(request): request.state.user == {"id": 7, "scopes": [...], "via": "api_key"}

    await ApiKeys.revoke_async(key_id, user_id=7)
    await ApiKeys.list_async(user_id=7)        # never returns the secret/hash

Clients send ``Authorization: Bearer lila_...`` or ``X-API-Key: lila_...``.
Scopes also count as permissions for ``permissions=[...]`` checks.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import secrets
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Column, DateTime, Integer, String, Text

from lila.core.base_model import BaseModel
from lila.core.cache import Cache
from lila.core.responses import JSONResponse

PREFIX = "lila_"
_CACHE_TTL = 30


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


class ApiKey(BaseModel):
    __tablename__ = "api_keys"
    __private_fields__ = ("key_hash",)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(120), nullable=False, default="API key")
    prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False, unique=True)
    scopes = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    active = Column(Integer, nullable=False, default=1)


class ApiKeys:
    @staticmethod
    def generate() -> Tuple[str, str]:
        prefix = secrets.token_hex(4)
        return f"{PREFIX}{prefix}_{secrets.token_urlsafe(32)}", prefix

    @classmethod
    async def create_async(cls, user_id: int, name: str = "API key", scopes: Optional[List[str]] = None,
                           expires_days: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        token, prefix = cls.generate()
        expires = _now() + _dt.timedelta(days=int(expires_days)) if expires_days else None
        row = await ApiKey.insert_async(
            user_id=int(user_id), name=str(name)[:120], prefix=prefix, key_hash=_hash(token),
            scopes=",".join(scopes or []), expires_at=expires,
        )
        return token, row

    @classmethod
    async def list_async(cls, user_id: int) -> List[Dict[str, Any]]:
        return await ApiKey.get_all_async(user_id=int(user_id), order_by="id", desc=True,
                                          select="id,name,prefix,scopes,expires_at,last_used_at,created_at")

    @classmethod
    async def revoke_async(cls, key_id: int, user_id: Optional[int] = None) -> bool:
        filters = {"id": int(key_id)}
        if user_id is not None:
            filters["user_id"] = int(user_id)
        from sqlalchemy import select as sa_select

        table = ApiKey.__table__
        stmt = sa_select(table.c.key_hash).where(table.c.id == int(key_id), table.c.active == 1)
        if user_id is not None:
            stmt = stmt.where(table.c.user_id == int(user_id))
        async with ApiKey.get_connection().transaction() as session:
            digest = (await session.execute(stmt)).scalar()
        if not digest:
            return False
        revoked = await ApiKey.delete_async(int(key_id))
        await Cache.delete_async(f"apikey:{digest}")  # effective immediately, not after the cache TTL
        return revoked

    @classmethod
    async def verify_async(cls, token: str) -> Optional[Dict[str, Any]]:
        """Returns ``{"id", "user_id", "scopes", ...}`` for a valid key, else None."""
        if not token or not token.startswith(PREFIX) or len(token) > 200:
            return None
        digest = _hash(token)
        cache_key = f"apikey:{digest}"
        cached = await Cache.get_async(cache_key)
        if cached == "invalid":
            return None
        if isinstance(cached, dict):
            return cached
        # Equality lookup on the SHA-256 (unique index); the hash itself is never read back.
        rows = await ApiKey.get_all_async(limit=1, key_hash=digest, select="id,user_id,prefix,scopes,expires_at")
        row = rows[0] if rows else None
        if row is None:
            await Cache.set_async(cache_key, "invalid", ttl=_CACHE_TTL)
            return None
        expires = row.get("expires_at")
        if isinstance(expires, str):
            expires = _dt.datetime.fromisoformat(expires)
        if expires and expires < _now():
            return None
        info = {
            "id": row["id"],
            "user_id": row["user_id"],
            "prefix": row["prefix"],
            "scopes": [s for s in (row.get("scopes") or "").split(",") if s],
        }
        await Cache.set_async(cache_key, info, ttl=_CACHE_TTL)
        # last_used_at, written at most once per cache period
        await ApiKey.update_async(row["id"], last_used_at=_now())
        return info


def token_from_request(request) -> Optional[str]:
    header = request.headers.get("x-api-key")
    if header:
        return header.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and auth[7:].strip().startswith(PREFIX):
        return auth[7:].strip()
    return None


async def authenticate_request(request, scopes: Optional[List[str]] = None):
    """Router hook: sets ``request.state.user``/``api_key`` or returns 401/403."""
    token = token_from_request(request)
    info = await ApiKeys.verify_async(token) if token else None
    if info is None:
        return JSONResponse({"success": False, "message": "Invalid or missing API key"}, status_code=401,
                            headers={"WWW-Authenticate": "Bearer"})
    if scopes:
        import fnmatch

        granted = info["scopes"]
        if not all(any(g == "*" or g == s or fnmatch.fnmatchcase(s, g) for g in granted) for s in scopes):
            return JSONResponse({"success": False, "message": "API key lacks the required scope"}, status_code=403)
    request.state.api_key = info
    request.state.user = {"id": info["user_id"], "scopes": info["scopes"], "via": "api_key"}
    return None
