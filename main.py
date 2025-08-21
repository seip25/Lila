from core.app import App
from app.routes.routes import routes
from app.routes.api import routes as api_routes
from core.middleware import Middleware
from app.config import PORT, HOST,DEBUG
from app.middlewares.default import LoggingMiddleware,IPBlockingMiddleware,URLBlockingMiddleware,MaliciousExtensionMiddleware,SensitivePathMiddleware,ErrorHandlerMiddleware
import itertools
import uvicorn
import asyncio
 
# English: Combining application and API routes into a single list.
# Español: Combinando las rutas de la aplicación y la API en una única lista.
all_routes = list(itertools.chain(routes, api_routes))

# English: Here we activate the admin panel with default settings.
# Español: Aquí activamos el panel de administrador con configuraciones predeterminadas.
# from app.routes.admin import Admin
# from app.models.user import User
# admin_routes=Admin(models=[User])
# all_routes = list(itertools.chain(routes, api_routes,admin_routes))
# English: Marker for the admin routes in main.py.
# Español: Marcador para las rutas de administrador en main.py.
#admin_marker   

cors=None

#English: CORS usage example
#Español : Ejemplo de utilización de CORS
# cors={
#     "origin": ["*"],
#     "allow_credentials" : True,
#     "allow_methods":["*"],
#     "allow_headers": ["*"]
# }      
# app = App(debug=True, routes=all_routes,cors=cors)

#English:necessary for cli command modify react cors for development
#Español:necesario para el comando cli modificar cors de react para desarrollo
#react_marker
    
# English: Initializing the application with debugging enabled and the combined routes.
# Español: Inicializando la aplicación con la depuración activada y las rutas combinadas.

app = App(
    debug= DEBUG,
    routes=all_routes,
    cors=cors,
    middleware=[
        Middleware(LoggingMiddleware),
        Middleware(IPBlockingMiddleware),
        Middleware(URLBlockingMiddleware),
        Middleware(MaliciousExtensionMiddleware),
        Middleware(SensitivePathMiddleware),
        Middleware(ErrorHandlerMiddleware),
    ]
)

#English: To ensure SEO (bots, AI), caching, and HTML hydration, uncomment these lines.
#Adding {% include "react/cache/index.html" %} to <div id="root">
#Español :Para tener seo (bots,ia) ,cache y que react hidrate el html ,descomenta estas lineas.
#Agregadando en <div id="root"> ,  {% include "react/cache/index.html"  %} 

# import subprocess
# import sys

# @app.on_event("startup")
# async def startup_event():
#     print("♻️ Prerender for react...")
#     url_with_port =f" http://{HOST}:{PORT}"
#     subprocess.Popen([
#     sys.executable, 
#     "-m", 
#     "cli.prerender",  
#     "--url", 
#     url_with_port.strip()
# ])


# English: Asynchronous main function to run the application server.
# Español: Función principal asíncrona para ejecutar el servidor de la aplicación.
async def main():
    # English: Starting the Uvicorn server with the application instance.
    # Español: Iniciando el servidor Uvicorn con la instancia de la aplicación.
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)

# English: Entry point for the script, running the main asynchronous function.
# Español: Punto de entrada del script, ejecutando la función principal asíncrona.
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # English: Gracefully shutting down the application on keyboard interrupt.
        # Español: Apagando la aplicación de manera ordenada al interrumpir con el teclado.
        print("Shutting down the application...")
        pass
