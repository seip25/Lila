from sqlalchemy import Table,Column,Integer,String,TIMESTAMP 
from core.database import Base
from database.connections import connection 
from argon2 import PasswordHasher 
 
ph = PasswordHasher()

class User(Base):
    __tablename__='users'
    id = Column(Integer, primary_key=True,autoincrement=True)
    name=Column( String(length=50), nullable=False)
    email=Column( String(length=50), unique=True)
    password=Column(String(length=150), nullable=False)
    token=Column(String(length=150), nullable=False)
    active=Column( Integer, nullable=False,default=1)
    created_at=Column( TIMESTAMP)

    #English : Example of how to use SQLAlchemy to make queries to the database
    #Español : Ejemplo de como poder utilizar SQLAlchemy para hacer consultas a la base de datos
    def get_all(limit : int =1000) ->  list:
        query = f"SELECT *  FROM users WHERE active =1  LIMIT :limit" 
        result = connection.query(query=query,params={"limit":limit}, return_rows=True)
        if result :
            return result.fetchall() if not result == None else []
        return []
    #English : Example of how to use SQLAlchemy to make queries to the database
    #Español : Ejemplo de como poder utilizar SQLAlchemy para hacer consultas a la base de datos
    def get_by_id(id:int) -> dict:
        query = f"SELECT *  FROM users WHERE id = :id AND active = 1 LIMIT 1"
        params ={id:id}
        result = connection.query(query=query,params=params, return_rows=True)
        return result.fetchone() if not result == None else None
    
#English : Example of how to use the class to make queries to the database
#Español : Ejemplo de como usar la clase para realizar consultas a la base de datos   
#users = User.get_all()
#user = User.get_by_id(1)
