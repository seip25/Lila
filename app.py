from core.app import App 
from routes.routes import routes
from routes.api import routes as api_routes
from core.env import PORT,HOST
import itertools
import uvicorn
import asyncio
   
all_routes = list(itertools.chain(routes,api_routes))

app = App(debug=True,routes=all_routes) 
 
async def main():
    uvicorn.run("app:app.start", host=HOST, port=PORT,reload=True)


if __name__ == "__main__":
    asyncio.run(main())
   
