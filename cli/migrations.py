import sys
import os
sys.path.insert(0, os.getcwd())

from sqlalchemy import Table,Column,Integer,String,TIMESTAMP 
from app.connections import connection
from core.database import Base #Import Base  for migrations in models
from app.models.user import User #Import models for migrations in models
import typer
import asyncio
import importlib
from pathlib import Path

def load_models():
    models_dir = Path("app/models")
    if models_dir.exists():
        for file in models_dir.glob("*.py"):
            if file.name != "__init__.py":
                module_name = f"app.models.{file.stem}"
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"Error loading model {module_name}: {e}")

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
        load_models()
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