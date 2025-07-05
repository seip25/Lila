from core.app import App
from app.routes.routes import routes
from app.routes.api import routes as api_routes

# English: Importing the host and port configurations from the environment settings.
# Español: Importando las configuraciones de host y puerto desde la configuración del entorno.
from core.env import PORT, HOST
import itertools
import uvicorn
import asyncio
 

# English: Combining application and API routes into a single list.
# Español: Combinando las rutas de la aplicación y la API en una única lista.
all_routes = list(itertools.chain(routes, api_routes))

# English: Here we activate the admin panel with default settings.
# Español: Aquí activamos el panel de administrador con configuraciones predeterminadas.
from app.routes.admin import Admin
from app.models.user import User
admin_routes=Admin(models=[User])
all_routes = list(itertools.chain(routes, api_routes,admin_routes))


# English: Initializing the application with debugging enabled and the combined routes.
# Español: Inicializando la aplicación con la depuración activada y las rutas combinadas.
app = App(debug=True, routes=all_routes)

#English: CORS usage example
#Español : Ejemplo de utilización de CORS
# cors={
#     "origin": ["*"],
#     "allow_credentials" : True,
#     "allow_methods":["*"],
#     "allow_headers": ["*"]
# }      
# app = App(debug=True, routes=all_routes,cors=cors)

# English: Asynchronous main function to run the application server.
# Español: Función principal asíncrona para ejecutar el servidor de la aplicación.
async def main():
    # English: Starting the Uvicorn server with the application instance.
    # Español: Iniciando el servidor Uvicorn con la instancia de la aplicación.
    uvicorn.run("main:app.start", host=HOST, port=PORT, reload=True)

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
