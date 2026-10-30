from sqlalchemy import Column, Integer, String, TIMESTAMP, func, DateTime, select
from lila.core.base_model import BaseModel
import datetime
import hashlib
import secrets
from app.connections import connection


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class LoginAttempt(BaseModel):
    __tablename__ = "login_attempts"
    _delete_logic = False

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), unique=True, index=True, nullable=False)
    attempts = Column(Integer, default=0)
    locked_at = Column(DateTime, nullable=True)

    def is_locked(self):
        if not self.locked_at:
            return False
        return _utcnow() < self.locked_at + datetime.timedelta(minutes=5)

    @classmethod
    async def get_lock_seconds_async(cls, email: str) -> int:
        """Returns remaining lockout seconds (0 when not locked)."""
        conn = cls.get_connection()
        async with conn.transaction() as session:
            stmt = select(cls).where(func.lower(cls.email) == str(email).strip().lower()).limit(1)
            result = await session.execute(stmt)
            row = result.scalars().first()
            if not row or not row.locked_at:
                return 0
            unlock_at = row.locked_at + datetime.timedelta(minutes=5)
            remaining = int((unlock_at - _utcnow()).total_seconds())
            return max(0, remaining)

    @classmethod
    async def record_attempt(cls, db, email: str, ip: str, success: bool):
        """Records a login attempt and handles locking logic."""
        email = str(email).strip().lower()
        if getattr(db, "is_async", False) or hasattr(db, "execute"):
            from sqlalchemy.ext.asyncio import AsyncSession

            if isinstance(db, AsyncSession):
                result = await db.execute(select(cls).filter_by(email=email))
                attempt = result.scalars().first()
            else:
                attempt = db.query(cls).filter_by(email=email).first()
        else:
            attempt = db.query(cls).filter_by(email=email).first()

        if not attempt:
            attempt = cls(email=email, attempts=0)
            db.add(attempt)

        if attempt.attempts is None:
            attempt.attempts = 0

        if success:
            attempt.attempts = 0
            attempt.locked_at = None
            db.add(LoginSuccessHistory(email=email, ip_address=ip))
        else:
            attempt.attempts += 1
            if attempt.attempts >= 5:
                attempt.locked_at = _utcnow()
            db.add(
                LoginAttemptHistory(
                    email=email, ip_address=ip, details=f"Attempt {attempt.attempts}"
                )
            )
        return attempt

    @classmethod
    def get_all(cls, select: str = "id,email,attempts,locked_at", limit: int = 1000, **filters):
        return super().get_all(select=select, limit=limit, **filters)

    @classmethod
    async def get_all_async(cls, select: str = "id,email,attempts,locked_at", limit: int = 1000, **filters):
        return await super().get_all_async(select=select, limit=limit, **filters)


class LoginAttemptHistory(BaseModel):
    __tablename__ = "login_attempt_history"
    _delete_logic = False

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), nullable=False)
    ip_address = Column(String(length=255), nullable=True)
    device = Column(String(length=255), nullable=True)
    details = Column(String(length=255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class LoginSuccessHistory(BaseModel):
    __tablename__ = "login_success_history"
    _delete_logic = False

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), nullable=False)
    ip_address = Column(String(length=255), nullable=True)
    device = Column(String(length=255), nullable=True)
    details = Column(String(length=255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class PasswordResetToken(BaseModel):
    __tablename__ = "password_reset_tokens"
    _delete_logic = False

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    token = Column(String(length=255), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    @classmethod
    def create_token(cls, db, user_id: int, expires_minutes=30):
        """Creates a reset token; only its SHA-256 hash is stored in the DB."""
        token = secrets.token_urlsafe(32)
        expires_at = _utcnow() + datetime.timedelta(minutes=expires_minutes)
        reset_token = cls(user_id=user_id, token=cls._hash(token), expires_at=expires_at)
        db.add(reset_token)
        return token

    @classmethod
    async def validate_token(cls, db, token: str):
        """Validates a token and returns the associated user_id if valid."""
        token_hash = cls._hash(token)
        if getattr(db, "is_async", False) or hasattr(db, "execute"):
            from sqlalchemy.ext.asyncio import AsyncSession

            if isinstance(db, AsyncSession):
                result = await db.execute(select(cls).filter_by(token=token_hash))
                reset_token = result.scalars().first()
            else:
                reset_token = db.query(cls).filter_by(token=token_hash).first()
        else:
            reset_token = db.query(cls).filter_by(token=token_hash).first()

        if not reset_token:
            return None
        if _utcnow() > reset_token.expires_at:
            db.delete(reset_token)
            return None
        return reset_token.user_id

    @classmethod
    def get_all(cls, select: str = "id,user_id,token,expires_at,created_at", limit: int = 1000, **filters):
        return super().get_all(select=select, limit=limit, **filters)

    @classmethod
    async def get_all_async(cls, select: str = "id,user_id,token,expires_at,created_at", limit: int = 1000, **filters):
        return await super().get_all_async(select=select, limit=limit, **filters)
