from sqlalchemy import Table,Column,Integer,String,TIMESTAMP
from sqlalchemy.orm import validates
from core.database import Base
from database.connections import connection
import secrets
import hashlib
import bcrypt

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

    def insert(params :dict )->bool:
        params["token"]=hashlib.sha256(secrets.token_hex(16).encode()).hexdigest()
        params["active"]=1
        params["password"]=bcrypt.hashpw(params["password"].encode('utf-8'),bcrypt.gensalt())
        placeholders =' ,'.join(f":{key}" for key in params.keys())
        columns =','.join(f"{key}" for key in params.keys() )
        
        query =f"INSERT INTO users ({columns}) VALUES({placeholders})"
        return connection.query(query,params)

#Example to execute querys with models SQLAlchemy
#usage mode for running queries (insert, select, update, etc.)

#User.insert({"name":"name","email":"example@example.com","password":"password"})


    
    