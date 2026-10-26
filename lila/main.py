from app.config import DEBUG, HOST, PORT, JIT, WORKERS
from app.routes.web.index import router as web_router
from app.routes.api.index import router as api_router
from app.routes.api.example import router as example_api_router
from app.routes.admin.index import router as admin_router
from lila.core.app import App
import os
import uvicorn

# api_marker
# auth_marker
# admin_marker

app = App(
    routes=[web_router, api_router, example_api_router, admin_router],
    debug=DEBUG,
    security=True,       # Cabeceras de seguridad y blindaje de rutas
    rate_limit=300,      # 300 req/min por IP (None para desactivar)
    logging=False,       # True para registrar peticiones en app/logs
    cors=True,           # Habilitar CORS
)

def main():
    if DEBUG:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
    else:
        workers = min((os.cpu_count() or 1) * 2 + 1, 8) if (str(WORKERS).lower() == "max" or WORKERS == 0) else int(WORKERS)
        print(f"🚀 Running Lila v2.0.0 on {HOST}:{PORT} with {workers} workers")
        uvicorn.run("main:app", host=HOST, port=PORT, reload=False, workers=workers)

if __name__ == "__main__":
    if JIT:
        os.environ["PYTHON_JIT"] = "1"
    main()
