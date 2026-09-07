from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import Session
from lila.core.base_model import BaseModel
from app.connections import connection
import secrets
import hashlib
import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

class User(BaseModel):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(length=50), nullable=False)
    email = Column(String(length=50), unique=True)
    password = Column(String(length=150), nullable=False)
    token = Column(String(length=150), nullable=True)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    @classmethod
    def get_all(cls, select: str = "id,email,name,active", limit: int = 1000, **filters):
        """Retrieves all users with default safe fields."""
        return super().get_all(select=select, limit=limit, **filters)
        
    @classmethod
    def get_all_async(cls, select: str = "id,email,name,active", limit: int = 1000, **filters):
        """Retrieves all users with default safe fields."""
        return super().get_all_async(select=select, limit=limit, **filters)

    @classmethod
    def get_by_email(cls, db: Session, email: str, active: int = 1):
        """Retrieves a user by email."""
        return db.query(cls).filter(cls.email == email, cls.active == active).first()

    @classmethod
    async def get_by_email_async(cls, email: str, active: int = 1):
        """Retrieves a user by email asynchronously with query deduplication."""
        cache_key = f"{cls.__tablename__}:get_by_email:{email}:{active}"
        async def _fetch():
            if not connection.is_async:
                db = connection.get_session()
                try:
                    return cls.get_by_email(db, email, active)
                finally:
                    db.close()

            from sqlalchemy import select as sa_select
            async with connection.transaction() as db:
                stmt = sa_select(cls).where(cls.email == email).where(cls.active == active)
                result = await db.execute(stmt)
                return result.scalars().first()

        return await cls.run_async(cache_key, _fetch)

    def set_password(self, password: str):
        """Hashes and sets the user's password."""
        self.password = ph.hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies the password against the stored hash."""
        try:
            return ph.verify(self.password, password)
        except Exception:
            return False

    @classmethod
    def check_login(cls, db: Session, email: str):
        return db.query(cls).filter(cls.email == email, cls.active == 1).first()

    @classmethod
    def check_for_email(cls, db: Session, email: str) -> bool:
        return db.query(cls).filter(cls.email == email).first() is not None

    @classmethod
    def insert(cls, db: Session, params: dict) -> 'User':
        hashed_password = cls.hash_password(params["password"])
        user = cls(
            name=params["name"],
            email=params["email"],
            password=hashed_password,
            token=hashlib.sha256(secrets.token_hex(16).encode()).hexdigest(),
            active=1,
            created_at=datetime.datetime.now()
        )
        db.add(user)
        return user

    @staticmethod
    def hash_password(password: str) -> str:
        return ph.hash(password)

    @staticmethod
    def validate_password(stored_hash: str, password: str) -> bool:
        try:
            return ph.verify(stored_hash, password)
        except VerifyMismatchError:
            return False

    @classmethod
    def update(cls, db: Session, id: int, data: dict) -> bool:
        user = cls.get_by_id(db, id)
        if not user:
            return False

        if "password" in data:
            data["password"] = cls.hash_password(data["password"])

        for field, value in data.items():
            setattr(user, field, value)

        db.commit()
        return True
