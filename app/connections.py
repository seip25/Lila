from core.database import Database
from sqlalchemy.orm import Session

#English : Example connection to a mysql database
#Español: Ejemplo de conexión a la base de datos con mysql
#config = {"type":"mysql","host":"127.0.0.1","user":"root","password":"password","database":"db_test","auto_commit":True}
#connection = Database(config=config)
#connection.connect()
#mysql_connection = connection

#English : Example connection to a psgr database
#Español: Ejemplo de conexión a la base de datos con psgr
# config = {"type":"postgresql","host":"localhost","port":5432,"user":"postgres","password":"root","database":"db_test","auto_commit":True}
# connection = Database(config=config)
# connection.connect()
#psgr_connection = connection

#English : Example connection to a sqlite database
#Español: Ejemplo de conexión a la base de datos con sqlite
config = {"type":"sqlite","database":"lila"} #lila.db
connection = Database(config=config)
connection.connect()

#Use for orm sqlalchemy abstraction
db_session=connection.get_session()