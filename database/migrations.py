from sqlalchemy import Table,Column,Integer,String,TIMESTAMP
from database.connections import connection
from core.database import Base
from models.user import User


# #Example of creating migrations for 'users'
# table_users = Table(
#     'users', connection.metadata,
#     Column('id', Integer, primary_key=True,autoincrement=True),
#     Column('name', String(length=50), nullable=False),
#     Column('email', String(length=50), unique=True),
#     Column('password', String(length=150), nullable=False),
#     Column('token', String(length=150), nullable=False),
#     Column('active', Integer,default=1, nullable=False),
#     Column('created_at', TIMESTAMP), 
# )

async def migrate(connection,refresh:bool=False)->bool:
    
    try:
        if refresh:
            connection.metadata.drop_all(connection.engine)
        # connection.prepare_migrate([table_users])#for tables
        # connection.migrate() 
        connection.migrate(use_base=True)#for models
        print("Migrations completed")
        
        return True
    except RuntimeError as e:
        print(e)
    
    
