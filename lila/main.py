from lila.core.app import App
from app.routes.web.index import routes
from app.routes.api.index import routes as api_routes 
from app.routes.api.example import routes as example_api_routes
from app.config import DEBUG, JIT, HOST, PORT
from lila.core.middleware import (
    Middleware,
    LoggingMiddleware,
    SecurityShieldMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    ErrorHandlerMiddleware,
)
from lila.core.logger import delete_old_logs
import itertools
import uvicorn
import os

# English: Combining web and API routes into a single list.
# Español: Combinando las rutas web y de la API en una única lista.
all_routes = list(itertools.chain(routes, api_routes, example_api_routes))

# English: Marker for auto-importing scaffold CRUD routes (used by lila-crud generator)
# Español: Marcador para importar automáticamente rutas CRUD del scaffold (usado por el generador lila-crud)
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
        uvicorn.run("main:app", host=HOST, port=PORT, reload=False, access_log=False,log_level="warning",workers=3) #workers (2 * 2num_cpu) + 1

if __name__ == "__main__":
    try:
        if JIT:
            os.environ["PYTHON_JIT"] = "1"
        main()
    except KeyboardInterrupt:
        print("Shutting down the application...")
        pass
