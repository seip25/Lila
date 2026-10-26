from sqlalchemy import Column, Integer, String, TIMESTAMP, func
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

class User(BaseModel):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(length=100), nullable=False)
    email = Column(String(length=120), unique=True, index=True)
    password = Column(String(length=255), nullable=False)
    token = Column(String(length=150), nullable=True)
    active = Column(Integer, nullable=False, default=1)
    
    # Better Auth OAuth support
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
        return PasswordHasher.verify(self.password, password)

    @classmethod
    def get_by_email(cls, db: Session, email: str, active: int = 1):
        return db.query(cls).filter(cls.email == email, cls.active == active).first()

    @classmethod
    async def get_by_email_async(cls, email: str, active: int = 1):
        from sqlalchemy import select
        conn = cls.get_connection()
        async with conn.transaction() as session:
            stmt = select(cls).where(cls.email == email, cls.active == active)
            res = await session.execute(stmt)
            return res.scalars().first()

    @classmethod
    def check_for_email(cls, db: Session, email: str) -> bool:
        return db.query(cls).filter(cls.email == email).first() is not None

    @classmethod
    def insert(cls, db: Session, params: dict) -> 'User':
        raw_pw = params.get("password") or secrets.token_urlsafe(16)
        hashed_password = PasswordHasher.hash(raw_pw)
        user = cls(
            name=params.get("name", "User"),
            email=params.get("email"),
            password=hashed_password,
            token=hashlib.sha256(secrets.token_hex(16).encode()).hexdigest(),
            active=1,
            oauth_provider=params.get("oauth_provider"),
            oauth_id=params.get("oauth_id"),
            avatar_url=params.get("avatar_url"),
            created_at=datetime.datetime.now()
        )
        db.add(user)
        return user
