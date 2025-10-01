from core.app import App
from app.routes.routes import routes
from app.routes.api import routes as api_routes
from core.middleware import Middleware
from app.config import PORT, HOST, DEBUG
from app.middlewares.defaults import (
    LoggingMiddleware,
    IPBlockingMiddleware,
    URLBlockingMiddleware,
    MaliciousExtensionMiddleware,
    SensitivePathMiddleware,
    ErrorHandlerMiddleware,
)
import itertools
import uvicorn
import asyncio

# English: Combining application and API routes into a single list.
# Español: Combinando las rutas de la aplicación y la API en una única lista.
all_routes = list(itertools.chain(routes, api_routes))

#English : Marker for the auth routes in main.py
#Español: Marcardor para añadir automaticamente rutas auth en main.py
# auth_marker

# English: Marker for the admin routes in main.py.
# Español: Marcador para las rutas de administrador en main.py.
# admin_marker
   
cors = None

# English: CORS usage example
# Español : Ejemplo de utilización de CORS
# cors={
#     "origin": ["*"],
#     "allow_credentials" : True,
#     "allow_methods":["*"],
#     "allow_headers": ["*"]
# }
# app = App(debug=True, routes=all_routes,cors=cors)

# English:necessary for cli command modify react cors for development
# Español:necesario para el comando cli modificar cors de react para desarrollo
# react_marker

middlewares = [
    Middleware(LoggingMiddleware),
    Middleware(IPBlockingMiddleware),
    Middleware(URLBlockingMiddleware),
    Middleware(MaliciousExtensionMiddleware),
    Middleware(SensitivePathMiddleware),
    Middleware(ErrorHandlerMiddleware)
]

# English: Initializing the application with debugging enabled and the combined routes.
# Español: Inicializando la aplicación con la depuración activada y las rutas combinadas.
app = App(debug=DEBUG, routes=all_routes, cors=cors, middleware=middlewares)

async def main():
    # English: Starting the Uvicorn server with the application instance.
    # Español: Iniciando el servidor Uvicorn con la instancia de la aplicación.
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down the application...")
        pass
