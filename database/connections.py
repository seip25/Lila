from core.database import Database


# config = {"type":"sqlite","database":"test"} #test.db
# connection = Database(config=config)
# connection.connect()

config = {"type":"mysql","host":"127.0.0.1","user":"root","password":"password","database":"db_test","auto_commit":True}
connection = Database(config=config)
connection.connect()
mysql_connection = connection