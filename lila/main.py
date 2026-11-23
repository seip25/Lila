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
    csp=True,            # Content-Security-Policy with nonces: <script{{ nonce_attr }}>
)
# lila:includes:start
# lila:includes:end


def main():
    from lila.core.config import server_graceful_timeout

    graceful_timeout = server_graceful_timeout()
    if DEBUG:
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            reload=True,
            timeout_graceful_shutdown=min(graceful_timeout, 3),
        )
    else:
        from lila.core.config import server_logging_options

        workers = min((os.cpu_count() or 1) * 2 + 1, 8) if (str(WORKERS).lower() == "max" or WORKERS == 0) else int(WORKERS)
        access_log, log_level = server_logging_options(debug=False)
        print(f"🚀 Running Lila on {HOST}:{PORT} with {workers} workers")
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            reload=False,
            workers=workers,
            access_log=access_log,
            log_level=log_level,
            timeout_graceful_shutdown=graceful_timeout,
        )


if __name__ == "__main__":
    main()
