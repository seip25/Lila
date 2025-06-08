from sqlalchemy import Table,Column,Integer,String,TIMESTAMP
from app.connections import connection
from core.database import Base #Import Base  for migrations in models
from app.models.user import User #Import models for migrations in models
import typer
import asyncio


app = typer.Typer()

#English:Example of creating migrations for 'users'
#Español: Ejemplo de creación de migraciones para 'users'
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

async def migrate_async(connection,refresh:bool=False)->bool:
    
    try:
        if refresh:
            connection.metadata.drop_all(connection.engine)
        # connection.prepare_migrate([table_users])#for tables
        # connection.migrate() 
        connection.migrate(use_base=True)#for models , always import models in the file
        print("Migrations completed")
        
        return True
    except RuntimeError as e:
        print(e)
    
    
@app.command()
def migrate(refresh: bool = False):
    """Run database migrations"""
    success = asyncio.run(migrate_async(connection, refresh))
    if not success:
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()