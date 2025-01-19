from core.app import App 
from routes.routes import routes
from routes.api import routes as api_routes
from core.env import PORT,HOST
import itertools
import uvicorn
import asyncio
#from database.migrations import migrate
#from database.connections import connection


all_routes = list(itertools.chain(routes,api_routes))

app = App(debug=True,routes=all_routes) 
 
async def main():
    #migrations = await migrate(connection) #execute migrates
   
    uvicorn.run("app:app.start", host=HOST, port=PORT,reload=True)


if __name__ == "__main__":
    asyncio.run(main())
   
