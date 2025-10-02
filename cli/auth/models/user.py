from sqlalchemy import Column, Integer, String, TIMESTAMP, func
from sqlalchemy.orm import Session, load_only
from core.database import Base
from app.connections import connection
import secrets
import hashlib
import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=50), nullable=False)
    email = Column(String(length=50), unique=True)
    password = Column(String(length=150), nullable=False)
    token = Column(String(length=150), nullable=True)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    @classmethod
    def get_all(cls,select: str = "id,email,name", limit: int = 1000):
        db = connection.get_session()
        try:
            column_names = [c.strip() for c in select.split(',')]
            columns_to_load = [getattr(cls, c) for c in column_names]
            result=db.query(cls).options(load_only(*columns_to_load)).filter(cls.active == 1).limit(limit).all()
            items = [
                {col: getattr(row, col) for col in column_names}
                for row in result
            ]
            return items
           
         
        finally:
            db.close()

    @classmethod
    def get_by_id(cls, db: Session, id: int):
        return db.query(cls).filter(cls.id == id, cls.active == 1).first()

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

     
    @staticmethod
    def get_all_without_orm(select: str = "id,email,name,created_at", limit: int = 1000) -> list:
        return connection.query(query=f"SELECT {select}  FROM users WHERE active = 1 LIMIT {limit}", return_rows=True)

    @staticmethod
    def get_by_id_without_orm(id: int, select="id,email,name") -> dict:
        params = {"id": id}
        return connection.query(query=f"SELECT {select}  FROM users WHERE id = :id AND active = 1 LIMIT 1", params=params, return_row=True)
