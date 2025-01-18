from core.database import Database

class User(Database): #mysql
    id: {"type": "INT", "primary_key": True, "auto_increment": True}
    email: {"type": "VARCHAR(100)", "not_null": True}#In mysql could be VARCHAR,etc
    password: {"type": "VARCHAR(100)", "not_null": True}
    name: {"type": "VARCHAR(50)"}
    token :  {"type":"VARCHAR(255)"} 

async def migrate(connection,refresh=False):
    models = [User]  # models list
    for model in models:
        model.set_connection(connection=connection)
        if refresh:
            model.drop_table()
        model.create_table()

# if __name__ == "__main__":
#     import sys
#     refresh = "refresh" in sys.argv
#     migrate(refresh)
