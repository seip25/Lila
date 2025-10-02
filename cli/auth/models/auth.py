from sqlalchemy import Column, Integer, String, TIMESTAMP, func,DateTime
from sqlalchemy.orm import load_only
from core.database import Base
import datetime
from app.connections import connection

class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), unique=True, index=True, nullable=False)
    attempts = Column(Integer, default=0)
    locked_at = Column(DateTime, nullable=True)

    def is_locked(self):
        if not self.locked_at:
            return False
        return datetime.datetime.utcnow() < self.locked_at + datetime.timedelta(minutes=5)
    @classmethod
    def get_all(cls,select: str = "id,email,attempts,locked_at", limit: int = 1000):
        db = connection.get_session()
        try:
            column_names = [c.strip() for c in select.split(',')]
            columns_to_load = [getattr(cls, c) for c in column_names]
            result=db.query(cls).options(load_only(*columns_to_load)).limit(limit).all()
            items = [
                {col: getattr(row, col) for col in column_names}
                for row in result
            ]
            return items

        finally:
            db.close()

class LoginAttemptHistory(Base):
    __tablename__ = "login_attemp_history"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), nullable=False)
    ip_address = Column(String(length=255), nullable=True)
    device = Column(String(length=255), nullable=True)
    details = Column(String(length=255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    @classmethod
    def get_all(cls,select: str = "id,email,ip_address,device,details,created_at", limit: int = 1000):
        db = connection.get_session()
        try:
            column_names = [c.strip() for c in select.split(',')]
            columns_to_load = [getattr(cls, c) for c in column_names]
            result=db.query(cls).options(load_only(*columns_to_load)).limit(limit).all()
            items = [
                {col: getattr(row, col) for col in column_names}
                for row in result
            ]
            return items
        finally:
            db.close()


class LoginSuccessHistory(Base):
    __tablename__ = "login_success_history"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), nullable=False)
    ip_address = Column(String(length=255), nullable=True)
    device = Column(String(length=255), nullable=True)
    details = Column(String(length=255), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    @classmethod
    def get_all(cls,select: str = "id,email,ip_address,device,details,created_at", limit: int = 1000):
        db = connection.get_session()
        try:
            column_names = [c.strip() for c in select.split(',')]
            columns_to_load = [getattr(cls, c) for c in column_names]
            result=db.query(cls).options(load_only(*columns_to_load)).limit(limit).all()
            items = [
                {col: getattr(row, col) for col in column_names}
                for row in result
            ]
            return items
        finally:
            db.close()

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(length=255), nullable=False, index=True)
    token = Column(String(length=255), unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    @classmethod
    def create_token(cls, db, email, token, expires_minutes=30):
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)
        reset_token = cls(email=email, token=token, created_at=datetime.datetime.utcnow(), expires_at=expires_at)
        db.add(reset_token)
        db.commit()
        return reset_token

    @classmethod
    def validate_token(cls, db, email, token):
        reset_token = db.query(cls).filter_by(email=email, token=token).order_by(cls.created_at.desc()).first()
        if not reset_token:
            return False
        if datetime.datetime.utcnow() > reset_token.expires_at:
            return False
        return True
    @classmethod
    def get_all(cls,select: str = "id,email,expires_at,created_at", limit: int = 1000):
        db = connection.get_session()
        try:
            column_names = [c.strip() for c in select.split(',')]
            columns_to_load = [getattr(cls, c) for c in column_names]
            result=db.query(cls).options(load_only(*columns_to_load)).limit(limit).all()
            items = [
                {col: getattr(row, col) for col in column_names}
                for row in result
            ]
            return items
        finally:
            db.close()