from app.config import DEBUG, HOST, PORT, WORKERS
from app.routes.web.index import router as web_router
from app.routes.api.index import router as api_router
from app.routes.api.example import router as example_api_router
from lila.core.app import App
import os
import uvicorn

# lila:imports
# api_marker
# auth_marker
# admin_marker

app = App(
    routes=[web_router, api_router, example_api_router],
    debug=DEBUG,
    security=True,       # Security headers and traversal shield
    rate_limit=300,      # 300 req/min per IP (None to disable)
    logging=False,       # True to log requests in app/logs/
    cors=True,           # Enable CORS
    gzip=True,           # Compress HTML/JSON/JS responses
    openapi=True,        # Mount /openapi.json and Swagger UI at /docs
    debug_html=DEBUG,    # Mount /debug dashboard in debug mode
)
# lila:includes:start
# lila:includes:end


def main():
    if DEBUG:
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            reload=True,
        )
    else:
        workers = min((os.cpu_count() or 1) * 2 + 1, 8) if (str(WORKERS).lower() == "max" or WORKERS == 0) else int(WORKERS)
        print(f"🚀 Running Lila v2.0 on {HOST}:{PORT} with {workers} workers")
        uvicorn.run("main:app", host=HOST, port=PORT, reload=False, workers=workers)


if __name__ == "__main__":
    main()
