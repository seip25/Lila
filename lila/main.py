from lila.core.app import App
from app.routes.web.index import routes
from app.routes.api.index import routes as api_routes 
from app.routes.api.example import routes as example_api_routes
from app.config import DEBUG, JIT, HOST, PORT, WORKERS
from lila.core.middleware import (
    Middleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    FlashMiddleware,
)
from lila.core.logger import delete_old_logs
import itertools
import uvicorn
import os

# Combine web and API routes into a single list
all_routes = list(itertools.chain(routes, api_routes, example_api_routes))

# Markers for CLI code generators
# api_marker
# auth_marker
# admin_marker

cors = None
# Example CORS configuration:
# cors = {
#     "origin": ["*"],
#     "allow_credentials": True,
#     "allow_methods": ["*"],
#     "allow_headers": ["*"],
# }

# Optional middlewares (SecurityHeadersMiddleware and FlashMiddleware are included by default in App)
middlewares = []

# Initialize Lila application
app = App(debug=DEBUG, routes=all_routes, cors=cors, middleware=middlewares)


def main():
    if DEBUG:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
    else:
        if str(WORKERS).lower() == "max" or WORKERS == 0:
            workers = min((os.cpu_count() or 1) * 2 + 1, 8)
        else:
            workers = int(WORKERS)
        uds_path = os.getenv("UDS_PATH")
        if uds_path:
            if os.path.exists(uds_path):
                try:
                    os.unlink(uds_path)
                except Exception:
                    pass
            os.makedirs(os.path.dirname(uds_path), exist_ok=True)
            print(f"🚀 Running Lila in UDS mode: {uds_path} with {workers} workers (uvloop + httptools)")
            uvicorn.run("main:app", uds=uds_path, reload=False, access_log=False, log_level="warning", workers=workers, loop="uvloop", http="httptools")
        else:
            print(f"🚀 Running Lila in TCP mode: {HOST}:{PORT} with {workers} workers (uvloop + httptools)")
            uvicorn.run("main:app", host=HOST, port=PORT, reload=False, access_log=False, log_level="warning", workers=workers, loop="uvloop", http="httptools")


if __name__ == "__main__":
    try:
        if JIT:
            os.environ["PYTHON_JIT"] = "1"
        main()
    except KeyboardInterrupt:
        print("Shutting down the application...")
        pass
