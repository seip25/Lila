from sqlalchemy import create_engine, MetaData,text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional

#for models 
Base = declarative_base()

class Database:
    def __init__(self,config:dict) -> None:
        self.type = config.get('type','sqlite')
        self.config = config
        self.connection=None
        self.metadata=MetaData()
        self.tables=[]
        self.auto_commit = self.config.get('auto_commit', False)


    def connect(self) ->bool:
        if self.type in ['mysql','postgresql','psgr']:
            user=self.config.get('user','root')
            password=self.config.get('password','')
            host = self.config.get('host','127.0.0.1')
            port = self.config.get('port',3306)
            database =self.config.get('database','db')
            type= 'postgresql' if self.type in ['postegresql','psg'] else self.type
            connector ='mysqlconnector'
            if self.type in ['postegresql','psg']:
                connector='psycopg2'
            isolation_level=self.config.get('isolation_level',None)

            try:
                self.engine=create_engine(f"{type}+{connector}://{user}:{password}@{host}:{port}/",isolation_level=isolation_level,execution_options={'autocommit': self.auto_commit})
            except SQLAlchemyError as e:
                print(f"Database connection error: {e}")
                return False
            
            if self.type == 'mysql':
                
                self.query(query=f"CREATE DATABASE IF NOT EXISTS {database}")
                self.query(query=f" USE {database}")
                
            self.engine=create_engine(f"{type}+{connector}://{user}:{password}@{host}:{port}/{database}",isolation_level=isolation_level,execution_options={'autocommit': self.auto_commit})
                    
        else:
            database=self.config.get('database','db')
            try:
                self.engine=create_engine(f"sqlite:///{database}.sqlite")
            except SQLAlchemyError as e:
                print(f"Create database, error: {e}")
                return False
        return True
        
    
    def prepare_migrate(self,tables: list)->None:
        self.tables.extend(tables)
    
    def migrate(self,use_base:bool=False):
        try:
            if use_base:
                Base.metadata.create_all(self.engine)
            else:
                self.metadata.create_all(self.engine)
            print("success migrations")
        except SQLAlchemyError as e:
            print(e)

    def query(self,query : str ,params :Optional[str]=None , return_rows:bool =False)->list | bool:
        try:
            with self.engine.connect() as connection:
                result=connection.execute(text(query),params or ())
            
                self.connection=connection
                if query.strip().upper().startswith(('CREATE','INSERT','UPDATE','DELETE')):
                    connection.commit()

            if return_rows :
                return [row for row in result]
            return True
        except SQLAlchemyError as e:
            print(f"Query error:{e}")
        return False
    
    def commit(self)->None:
        if self.connection and not self.auto_commit:
            try:
                self.connection.commit()
            except SQLAlchemyError as e:
                print(f"Commit error: {e}")
    
    def close(self) -> None:
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                print("Connection closed.")
            except SQLAlchemyError as e:
                print(f"Close connection error: {e}")

          
