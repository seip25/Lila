from core.database import Database

#English : Example connection to a sqlite database
#Español: Ejemplo de conexión a la base de datos con sqlite
config = {"type":"sqlite","database":"test"} #test.db
connection = Database(config=config)
connection.connect()


#English : Example connection to a mysql database
#Español: Ejemplo de conexión a la base de datos con mysql
#config = {"type":"mysql","host":"127.0.0.1","user":"root","password":"password","database":"db_test","auto_commit":True}
#connection = Database(config=config)
#connection.connect()
#mysql_connection = connection
