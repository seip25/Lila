from core.app import App
from app.routes.routes import routes
from app.routes.api import routes as api_routes
from app.config import DEBUG, JIT, HOST, PORT
from core.middleware import (
    Middleware,
    LoggingMiddleware,
    SecurityShieldMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    ErrorHandlerMiddleware,
)
from core.logger import delete_old_logs
import itertools
import uvicorn
import asyncio
import os

# English: Combining application and API routes into a single list.
# Español: Combinando las rutas de la aplicación y la API en una única lista.
all_routes = list(itertools.chain(routes, api_routes))

#English : Marker for the api routes in main.py (also used by scaffold generator)
#Español: Marcardor para añadir automaticamente rutas api en main.py (también usado por generador de scaffold)
# api_marker

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



#English : Example middlewares with logger,security,ip rate limit ,error handler,Xss
#Español : Ejemplo de middlewares con logger, security,ip rate limit,error hanlder, Xss
# middlewares = [
#     Middleware(LoggingMiddleware),
#     Middleware(SecurityHeadersMiddleware),
#     Middleware(SecurityShieldMiddleware),
#     Middleware(RateLimitMiddleware),
#     Middleware(ErrorHandlerMiddleware)
#      ]

middlewares = [
    Middleware(ErrorHandlerMiddleware),
    Middleware(SecurityHeadersMiddleware)
]

# English: Initializing the application with debugging enabled and the combined routes.
# Español: Inicializando la aplicación con la depuración activada y las rutas combinadas.
app = App(debug=DEBUG, routes=all_routes, cors=cors, middleware=middlewares)

def main():
    if DEBUG:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
    else:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=False, access_log=False,log_level="warning")

if __name__ == "__main__":
    try:
        if JIT:
            os.environ["PYTHON_JIT"] = "1"
        main()
    except KeyboardInterrupt:
        print("Shutting down the application...")
        pass
