from sqlalchemy import Table,Column,Integer,String,TIMESTAMP
from database.connections import connection
from core.database import Base


#Example of creating migrations for 'users'
table_users = Table(
    'users', connection.metadata,
    Column('id', Integer, primary_key=True,autoincrement=True),
    Column('name', String(length=50), nullable=False),
    Column('email', String(length=50), unique=True),
    Column('password', String(length=150), nullable=False),
    Column('token', String(length=150), nullable=False),
    Column('active', Integer,default=1, nullable=False),
    Column('created_at', TIMESTAMP), 
)

#For models
class User(Base):
    __tablename__='users'
    id = Column(Integer, primary_key=True,autoincrement=True)
    name=Column( String(length=50), nullable=False)
    email=Column( String(length=50), unique=True)
    password=Column(String(length=150), nullable=False)
    token=Column(String(length=150), nullable=False)
    active=Column( Integer,default=1, nullable=False)
    created_at=Column( TIMESTAMP)

async def migrate(connection,refresh:bool=False)->bool:
    
    try:
        if refresh:
            connection.metadata.drop_all(connection.engine)
        connection.prepare_migrate([table_users])#for tables
        connection.migrate() 
        connection.migrate(use_base=True)#for models
        print("Migrations completed")
        
        return True
    except RuntimeError as e:
        print(e)
    
    
