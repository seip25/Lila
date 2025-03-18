from sqlalchemy import Table, Column, Integer, String, TIMESTAMP
from sqlalchemy.orm import Session
from core.database import Base
from database.connections import connection
from argon2 import PasswordHasher

ph = PasswordHasher()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(length=50), nullable=False)
    email = Column(String(length=50), unique=True)
    password = Column(String(length=150), nullable=False)
    token = Column(String(length=150), nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP)

    # English : Example of how to use SQLAlchemy to make queries to the database
    # Español : Ejemplo de como poder utilizar SQLAlchemy para hacer consultas a la base de datos
    def get_all(select: str = "id,email,name", limit: int = 1000) -> list:
        query = f"SELECT {select}  FROM users WHERE active =1  LIMIT {limit}"
        print(query)
        result = connection.query(query=query,return_rows=True)
        return result 

    # English : Example of how to use SQLAlchemy to make queries to the database
    # Español : Ejemplo de como poder utilizar SQLAlchemy para hacer consultas a la base de datos
    def get_by_id(id: int, select="id,email,name") -> dict:
        query = f"SELECT {select}  FROM users WHERE id = :id AND active = 1 LIMIT 1"
        params = {"id": id}
        row = connection.query(query=query, params=params,return_row=True)
        return row

    # English: Example using ORM abstraction in SQLAlchemy
    # Español : Ejemplo usando abstracción de ORM en SQLAlchemy
    @classmethod
    def get_all_orm(cls, db: Session, limit: int = 1000):
        result = db.query(cls).filter(cls.active == 1).limit(limit).all()
        return result


# English : Example of how to use the class to make queries to the database
# Español : Ejemplo de como usar la clase para realizar consultas a la base de datos
# users = User.get_all()
# user = User.get_by_id(1)
