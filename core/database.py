import sqlite3
import mysql.connector
#psycopg2


class DatabaseConnection:
    def __init__(self, config: dict):
        self.engine = config.get("engine")  # sqlite, mysql
        self.config = config
        self.connection = None

    def connect(self):
        if self.engine == "sqlite":
            db =self.config.get("database")
            self.connection = sqlite3.connect(f"{db}.sqlite")
        elif self.engine == "mysql":
            self.connection = mysql.connector.connect(
                host=self.config.get("host"),
                user=self.config.get("user"),
                password=self.config.get("password"),
                database=self.config.get("database"),
                charset='utf8'
            )
        # elif self.engine == "postgresql":
        #     self.connection = psycopg2.connect(
        #         host=self.config.get("host"),
        #         user=self.config.get("user"),
        #         password=self.config.get("password"),
        #         dbname=self.config.get("database"),
        #     )
        else:
            raise ValueError("Unsupported database engine")
        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()


class Database:
    connection = None
    db_engine="sqlite"
    
    def __init__(cls,connection) -> None:
        cls.set_connection(connection=connection)

    @classmethod
    def name_table(cls):
        return f"{cls.__name__.lower()}s"

    @classmethod
    def set_connection(cls, connection):
        print(connection)
        if isinstance(connection, mysql.connector.MySQLConnection ):
            cls.db_engine = "mysql"
        elif isinstance(connection,mysql.connector.connection_cext.CMySQLConnection):
            cls.db_engine="mysql"
        elif isinstance(connection, sqlite3.Connection):
            cls.db_engine = "sqlite"
        else:
            raise ValueError("Unsupported database connection type")
        cls.connection = connection

    @classmethod
    def execute(cls, query, params=None):
        try:
            cursor = cls.connection.cursor()
            cursor.execute(query, params or ())
            if query.strip().upper().startswith("SELECT"):
                return cursor
            cls.connection.commit()
            cursor.close()
            return cursor
        except RuntimeError as e:
            print(f"{e}")
            return False

    @classmethod
    def create_table(cls):
        fields = []
        for attr, options in cls.__annotations__.items():
            field = f"{attr} {options['type']}"
            if options.get("primary_key"):
                field += " PRIMARY KEY"
            if cls.db_engine == "sqlite" and options.get("autoincrement"):
                field += " AUTOINCREMENT"
            elif cls.db_engine == "mysql" and options.get("auto_increment") :
                field += " AUTO_INCREMENT"
            if options.get("not_null"):
                field += " NOT NULL"
            if options.get("default") is not None:
                field += f" DEFAULT {options['default']}"
            fields.append(field)
        print(cls.db_engine)
        query = f"CREATE TABLE {cls.name_table()} ({', '.join(fields)});"
        cls.execute(query)


    @classmethod
    def drop_table(cls):
        query = f"DROP TABLE IF EXISTS {cls.name_table()};"
        cls.execute(query)
    
    @classmethod
    def str_engine(cls):
        s= "?" if cls.db_engine =="sqlite" else "%s"
        return s
  