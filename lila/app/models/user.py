from sqlalchemy import Column, Integer, String, TIMESTAMP, func, select
from sqlalchemy.orm import Session
from lila.core.base_model import BaseModel
from lila.core.auth import PasswordHasher
try:
    from app.connections import connection
except ImportError:
    from lila.core.database import db as connection
import secrets
import hashlib
import datetime


def _looks_hashed(value: str) -> bool:
    return isinstance(value, str) and value.startswith(("$argon2", "$scrypt$"))


class User(BaseModel):
    __tablename__ = "users"
    # Never serialize credentials through to_dict()/JSON/session cookies.
    __private_fields__ = ("password", "token")

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(length=100), nullable=False)
    email = Column(String(length=120), unique=True, index=True)
    password = Column(String(length=255), nullable=False)
    token = Column(String(length=150), nullable=True)
    active = Column(Integer, nullable=False, default=1)

    # Better Auth OAuth support fields
    oauth_provider = Column(String(length=50), nullable=True)
    oauth_id = Column(String(length=150), nullable=True)
    avatar_url = Column(String(length=255), nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    @classmethod
    def get_all(cls, select: str = "id,email,name,active,oauth_provider,created_at", limit: int = 1000, **filters):
        return super().get_all(select=select, limit=limit, **filters)

    def set_password(self, password: str):
        self.password = PasswordHasher.hash(password)

    def check_password(self, password: str) -> bool:
        return PasswordHasher.verify(self.password or "", password)

    @classmethod
    def get_by_email(cls, db: Session, email: str, active: int = 1):
        return (
            db.query(cls)
            .filter(func.lower(cls.email) == str(email).strip().lower(), cls.active == active)
            .first()
        )

    @classmethod
    async def get_by_email_async(cls, email: str, active: int = 1):
        conn = cls.get_connection()
        async with conn.transaction() as session:
            stmt = select(cls).where(
                func.lower(cls.email) == str(email).strip().lower(), cls.active == active
            )
            res = await session.execute(stmt)
            return res.scalars().first()

    @classmethod
    async def get_by_id_with_password_async(cls, user_id):
        """Returns the ORM row (including password) for auth checks only."""
        conn = cls.get_connection()
        async with conn.transaction() as session:
            stmt = select(cls).where(cls.id == user_id, cls.active == 1).limit(1)
            res = await session.execute(stmt)
            return res.scalars().first()

    @classmethod
    def check_for_email(cls, db: Session, email: str) -> bool:
        return (
            db.query(cls).filter(func.lower(cls.email) == str(email).strip().lower()).first()
            is not None
        )

    @classmethod
    def insert(cls, db: Session = None, params: dict = None, **values) -> "User":
        """Supports both ``User.insert(db, params)`` (v1) and ``User.insert(**values)``."""
        if isinstance(db, dict) and params is None:
            values = {**db, **values}
            db = None
        elif params:
            values = {**params, **values}

        raw_pw = values.pop("password", None) or secrets.token_urlsafe(16)
        if not _looks_hashed(raw_pw):
            raw_pw = PasswordHasher.hash(raw_pw)

        user = cls(
            name=values.pop("name", "User"),
            email=str(values.pop("email", "")).strip().lower() or None,
            password=raw_pw,
            token=values.pop("token", None) or hashlib.sha256(secrets.token_hex(16).encode()).hexdigest(),
            active=int(values.pop("active", 1) or 1),
            oauth_provider=values.pop("oauth_provider", None),
            oauth_id=values.pop("oauth_id", None),
            avatar_url=values.pop("avatar_url", None),
            created_at=values.pop("created_at", datetime.datetime.now()),
        )
        if db is not None:
            db.add(user)
            return user
        return super().insert(instance=user)

    @classmethod
    async def insert_async(cls, instance=None, **values):
        password = values.get("password")
        if password and not _looks_hashed(str(password)):
            values["password"] = await PasswordHasher.hash_async(str(password))
        if values.get("email"):
            values["email"] = str(values["email"]).strip().lower()
        return await super().insert_async(instance, **values)

    @classmethod
    async def update_async(cls, id_val, values: dict = None, **kwargs):
        payload = dict(values or {})
        payload.update(kwargs)
        password = payload.get("password")
        if password and not _looks_hashed(str(password)):
            payload["password"] = await PasswordHasher.hash_async(str(password))
        return await super().update_async(id_val, payload)
