from sqlalchemy import Column, Integer, String, TIMESTAMP, func, DateTime
from lila.core.base_model import BaseModel
import datetime
import secrets
from app.connections import connection

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
        return datetime.datetime.utcnow() < self.locked_at + datetime.timedelta(minutes=5)

    @classmethod
    def record_attempt(cls, db, email: str, ip: str, success: bool):
        """Records a login attempt and handles locking logic."""
        attempt = db.query(cls).filter_by(email=email).first()
        if not attempt:
            attempt = cls(email=email, attempts=0)
            db.add(attempt)
        
        if attempt.attempts is None:
            attempt.attempts = 0

        if success:
            attempt.attempts = 0
            attempt.locked_at = None
            # Record success in history
            success_record = LoginSuccessHistory(email=email, ip_address=ip)
            db.add(success_record)
        else:
            attempt.attempts += 1
            if attempt.attempts >= 5:
                attempt.locked_at = datetime.datetime.utcnow()
            # Record attempt in history
            attempt_record = LoginAttemptHistory(email=email, ip_address=ip, details=f"Attempt {attempt.attempts}")
            db.add(attempt_record)
        
        return attempt

    @classmethod
    def get_all(cls, select: str = "id,email,attempts,locked_at", limit: int = 1000, **filters):
        return super().get_all(select=select, limit=limit, **filters)

    @classmethod
    def get_all_async(cls, select: str = "id,email,attempts,locked_at", limit: int = 1000, **filters):
        return super().get_all_async(select=select, limit=limit, **filters)


class LoginAttemptHistory(BaseModel):
    __tablename__ = "login_attemp_history"
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
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    @classmethod
    def create_token(cls, db, user_id: int, expires_minutes=30):
        """Creates a new password reset token for a user."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)
        reset_token = cls(
            user_id=user_id, 
            token=token, 
            expires_at=expires_at
        )
        db.add(reset_token)
        return token

    @classmethod
    def validate_token(cls, db, token: str) -> int | None:
        """Validates a token and returns the associated user_id if valid."""
        reset_token = db.query(cls).filter_by(token=token).first()
        if not reset_token:
            return None
        if datetime.datetime.utcnow() > reset_token.expires_at:
            db.delete(reset_token)
            return None
        return reset_token.user_id

    @classmethod
    def get_all(cls, select: str = "id,user_id,token,expires_at,created_at", limit: int = 1000, **filters):
        return super().get_all(select=select, limit=limit, **filters)

    @classmethod
    def get_all_async(cls, select: str = "id,user_id,token,expires_at,created_at", limit: int = 1000, **filters):
        return super().get_all_async(select=select, limit=limit, **filters)
