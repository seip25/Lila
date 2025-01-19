from sqlalchemy import Table,Column,Integer,String,TIMESTAMP
from sqlalchemy.orm import validates
from core.database import Base
from database.connections import connection
import secrets
import hashlib
import bcrypt
import datetime

class User(Base):
    __tablename__='users'
    id = Column(Integer, primary_key=True,autoincrement=True)
    name=Column( String(length=50), nullable=False)
    email=Column( String(length=50), unique=True)
    password=Column(String(length=150), nullable=False)
    token=Column(String(length=150), nullable=False)
    active=Column( Integer, nullable=False,default=1)
    created_at=Column( TIMESTAMP)

    def validate_password(stored_hash :str, password:str)->bool:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))

    def insert(params: dict) -> bool | str:
        params["token"] = hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()
        params["active"] = 1
        params["password"] = bcrypt.hashpw(
            params["password"].encode("utf-8"), bcrypt.gensalt()
        )
        date = datetime.datetime.now()
        print(date)
        params["created_at"] = date
        placeholders = " ,".join(f":{key}" for key in params.keys())
        columns = ",".join(f"{key}" for key in params.keys())

        query = f"INSERT INTO users ({columns}) VALUES({placeholders})"
        result = connection.query(query, params)
        if result:
            return params["token"]

        return False
    
    def check_email(email: str) -> bool:
        query = f"SELECT id FROM users WHERE email= :email ORDER BY id DESC LIMIT 1"
        params = {"email": email}
        result = connection.query(query=query, params=params, return_rows=True)
        if result:
            return False if result.fetchone() == None else True
             
        return False

    def check_login(email: str) -> bool | list:
        query = f"SELECT password,token  FROM users WHERE email= :email AND active = 1 ORDER BY id DESC LIMIT 1"
        params = {"email": email}
        result = connection.query(query=query, params=params, return_rows=True)
        if result:
            result = result.fetchone()
        return result

#Example to execute querys with models SQLAlchemy
#usage mode for running queries (insert, select, update, etc.)

#User.insert({"name":"name","email":"example@example.com","password":"password"})


    
    