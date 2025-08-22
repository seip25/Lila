from abc import ABC, abstractmethod
from starlette.middleware.base import BaseHTTPMiddleware
from core.responses import HTMLResponse, JSONResponse
from core.request import Request
from core.logger import Logger
from datetime import datetime
import json
import os
import traceback
import sys
from typing import Any
from app.config import PATH_SECURITY
from app.config import SENSITIVE_PATHS


class BaseSecurityMiddleware(BaseHTTPMiddleware, ABC):
    def __init__(self, app, config_file: str, default_value: Any):
        super().__init__(app)
        self.config_file = config_file
        self.default_value = default_value
        self.data = self.load_data()

    def load_data(self):
        try:
            if not os.path.exists(self.config_file):
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                with open(self.config_file, "w") as file:
                    json.dump(self.default_value, file, indent=4)
                return self.default_value

            with open(self.config_file, "r") as file:
                content = file.read().strip()
                if not content:
                    with open(self.config_file, "w") as file:
                        json.dump(self.default_value, file, indent=4)
                    return self.default_value

                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    with open(self.config_file, "w") as file:
                        json.dump(self.default_value, file, indent=4)
                    return self.default_value

        except Exception as e:
            Logger.error(f"Error loading {self.config_file}: {str(e)}")
            return self.default_value

    def save_data(self, data):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w") as file:
                json.dump(data, file, indent=4)
        except Exception as e:
            Logger.error(f"Error saving {self.config_file}: {str(e)}")

    async def is_blocked(self, key: str, request: Request) -> bool:
        if key in self.data:
            expiration_time = datetime.fromisoformat(self.data[key]["expiration_time"])
            if datetime.now() < expiration_time:
                req = await Logger.request(request=request)
                Logger.warning(f"Blocked by {self.__class__.__name__}: {key} \n {req}")
                return True
        return False

    @abstractmethod
    async def check_request(self, request: Request) -> bool:
        pass

    @abstractmethod
    async def handle_blocked_request(self, request: Request) -> HTMLResponse:
        pass

    async def dispatch(self, request, call_next):
        if await self.check_request(request):
            return await self.handle_blocked_request(request)

        response = await call_next(request)
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            exc_type, exc_value, exc_tb = sys.exc_info()

            if exc_tb:
                tb = exc_tb
                while tb.tb_next:
                    tb = tb.tb_next

                frame = tb.tb_frame
                filename = frame.f_code.co_filename
                lineno = tb.tb_lineno
                function = frame.f_code.co_name

                error_info = {
                    "type": exc_type.__name__,
                    "message": str(e),
                    "file": filename,
                    "line": lineno,
                    "function": function,
                    "traceback": traceback.format_exc(),
                }

                Logger.error(
                    f"Error: {error_info['type']} in {error_info['file']}:{error_info['line']}"
                )
                Logger.error(f"Function: {error_info['function']}")
                Logger.error(f"Message: {error_info['message']}")
                Logger.error(f"Traceback:\n{error_info['traceback']}")

            return JSONResponse(
                {"error": "Internal Server Error", "success": False}, status_code=500
            )


class IPBlockingMiddleware(BaseSecurityMiddleware):
    def __init__(self, app, blocked_ips_file=f"{PATH_SECURITY}/blocked_ips.json"):
        super().__init__(app, blocked_ips_file, default_value={})

    async def check_request(self, request: Request) -> bool:
        client_ip = request.client.host
        return await self.is_blocked(client_ip, request)

    async def handle_blocked_request(self, request: Request) -> HTMLResponse:
        return HTMLResponse(
            content="<h1>Access Denied</h1><p>Your IP has been temporarily blocked.</p>",
            status_code=403,
        )


class URLBlockingMiddleware(BaseSecurityMiddleware):
    def __init__(self, app, blocked_urls_file=f"{PATH_SECURITY}blocked_urls.json"):
        super().__init__(app, blocked_urls_file, default_value={})

    async def check_request(self, request: Request) -> bool:
        url_path = request.url.path
        return await self.is_blocked(url_path, request)

    async def handle_blocked_request(self, request: Request) -> HTMLResponse:
        return HTMLResponse(
            content="<h1>Access Denied</h1><p>This URL has been temporarily blocked.</p>",
            status_code=403,
        )


class MaliciousExtensionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, malicious_extensions=None, block_duration_hours=6):
        super().__init__(app)
        self.malicious_extensions = malicious_extensions or [
            ".php",
            ".asp",
            ".jsp",
            ".aspx",
        ]
        self.block_duration_hours = block_duration_hours

    async def dispatch(self, request, call_next):
        url_path = request.url.path.lower()

        if any(ext in url_path for ext in self.malicious_extensions):
            client_ip = request.client.host
            Logger.warning(f"Malicious extension detected from {client_ip}: {url_path}")
            return HTMLResponse(
                content="<h1>Access Denied</h1><p>Malicious URL detected.</p>",
                status_code=403,
            )

        response = await call_next(request)
        return response


class SensitivePathMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app, sensitive_paths_file=f"{PATH_SECURITY}sensitive_paths.json"
    ):
        super().__init__(app)
        self.sensitive_paths = self.load_sensitive_paths(sensitive_paths_file)

    def load_sensitive_paths(self, file_path):
        default_paths = SENSITIVE_PATHS
        try:
            if not os.path.exists(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w") as file:
                    json.dump(default_paths, file, indent=4)
                return default_paths

            with open(file_path, "r") as file:
                content = file.read().strip()
                if not content:
                    with open(file_path, "w") as file:
                        json.dump(default_paths, file, indent=4)
                    return default_paths

                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    with open(file_path, "w") as file:
                        json.dump(default_paths, file, indent=4)
                    return default_paths

        except Exception as e:
            Logger.error(f"Error loading sensitive paths: {str(e)}")
            return default_paths

    async def dispatch(self, request, call_next):
        url_path = request.url.path.lower()
        body = await request.body()
        body_str = str(body).lower()

        if any(path in url_path or path in body_str for path in self.sensitive_paths):
            client_ip = request.client.host
            Logger.warning(f"Sensitive path detected from {client_ip}: {url_path}")
            return HTMLResponse(
                content="<h1>Access Denied</h1><p>Sensitive path detected.</p>",
                status_code=403,
            )

        response = await call_next(request)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_extensions=None, exclude_paths=None):
        super().__init__(app)
        self.exclude_extensions = exclude_extensions or {
            ".js",
            ".css",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".ico",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
        }
        self.exclude_paths = exclude_paths or {
            "public",
            "static",
            "assets",
            "favicon.ico",
        }

    async def should_log(self, path: str) -> bool:
        path_lower = path.lower()
        if any(path_lower.endswith(ext) for ext in self.exclude_extensions):
            return False
        if any(excluded in path_lower for excluded in self.exclude_paths):
            return False
        return True

    async def dispatch(self, request, call_next):
        if await self.should_log(request.url.path):
            Logger.info(await Logger.request(request=request))

        response = await call_next(request)
        return response
