from starlette.middleware.base import BaseHTTPMiddleware
from core.responses import JSONResponse, HTMLResponse
from core.request import Request
from core.logger import Logger
from datetime import datetime, timedelta
import json
import os


# English: Load data from a JSON file. If the file doesn't exist, is empty, or invalid, it initializes it with a default value.
# Español: Cargar datos desde un archivo JSON. Si el archivo no existe, está vacío o es inválido, lo inicializa con un valor por defecto.
def load_blocked_data(file_path, default_value):
    try:
        # English: Check if the file exists. If not, create it with the default value.
        # Español: Verificar si el archivo existe. Si no, crearlo con el valor por defecto.
        if not os.path.exists(file_path):
            with open(file_path, "w") as file:
                json.dump(default_value, file, indent=4)
            return default_value

        # English: Load the file and check if it's empty or invalid.
        # Español: Cargar el archivo y verificar si está vacío o es inválido.
        with open(file_path, "r") as file:
            content = file.read().strip()
            if not content:  # English: If the file is empty.
                # Español: Si el archivo está vacío.
                with open(file_path, "w") as file:
                    json.dump(default_value, file, indent=4)
                return default_value

            # English: Try to parse the JSON content.
            # Español: Intentar parsear el contenido JSON.
            try:
                return json.loads(content)
            except json.JSONDecodeError:  # English: If the JSON is invalid.
                # Español: Si el JSON es inválido.
                with open(file_path, "w") as file:
                    json.dump(default_value, file, indent=4)
                return default_value

    except Exception as e:
        Logger.error(f"Error loading {file_path}: {str(e)}")
        return default_value


# English: Save blocked IPs or URLs to a JSON file.
# Español: Guardar IPs o URLs bloqueadas en un archivo JSON.
def save_blocked_data(file_path, data):
    try:
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        Logger.error(f"Error saving {file_path}: {str(e)}")


# English: Check if an IP or URL is blocked.
# Español: Verificar si una IP o URL está bloqueada. 
async def is_blocked(blocked_data, key, request: Request):
    if key in blocked_data:
        expiration_time = datetime.fromisoformat(blocked_data[key]["expiration_time"])
        if datetime.now() < expiration_time:
            req=await Logger.request(request=request)
            Logger.warning(f"Blocked: {key} \n {req}")
            return True
    return False


# English: ErrorHandlerMiddleware to handle unhandled exceptions and security checks.
# Español: ErrorHandlerMiddleware para manejar excepciones no controladas y validaciones de seguridad.
class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        blocked_ips_file="system/security/blocked_ips.json",
        blocked_urls_file="system/security/blocked_urls.json",
        sensitive_paths_file="system/security/sensitive_paths.json",
    ):
        super().__init__(app)
        self.blocked_ips_file = blocked_ips_file
        self.blocked_urls_file = blocked_urls_file
        self.sensitive_paths_file = sensitive_paths_file

        # English: Load blocked IPs, URLs, and sensitive paths.
        # Español: Cargar IPs bloqueadas, URLs bloqueadas y rutas sensibles.
        self.blocked_ips = load_blocked_data(blocked_ips_file, default_value={})
        self.blocked_urls = load_blocked_data(blocked_urls_file, default_value={})
        self.sensitive_paths = load_blocked_data(sensitive_paths_file, default_value=[])

    async def dispatch(self, request, call_next):
        try:
            # English: Security checks before logging the request.
            # Español: Validaciones de seguridad antes de registrar la solicitud.
            client_ip = request.client.host
            url_path = request.url.path
            query_params = str(request.query_params)
            body = await request.body()

            # English: Check if the IP is blocked.
            # Español: Verificar si la IP está bloqueada.
            if await is_blocked(self.blocked_ips, client_ip, request=request):
                return HTMLResponse(
                    content="<h1>Access Denied</h1><p>Your IP has been temporarily blocked.</p>",
                    status_code=403,
                )

            # English: Check if the URL is blocked.
            # Español: Verificar si la URL está bloqueada.
            if await is_blocked(self.blocked_urls, url_path, request=request):
                return HTMLResponse(
                    content="<h1>Access Denied</h1><p>This URL has been temporarily blocked.</p>",
                    status_code=403,
                )

            # English: Block malicious file extensions.
            # Español: Bloquear extensiones de archivo maliciosas.
            malicious_extensions = [".php", ".asp", ".jsp", ".aspx"]
            if any(ext in url_path for ext in malicious_extensions):
                self.blocked_ips[client_ip] = {
                    "expiration_time": (datetime.now() + timedelta(hours=6)).isoformat()
                }
                save_blocked_data(self.blocked_ips_file, self.blocked_ips)
                return HTMLResponse(
                    content="<h1>Access Denied</h1><p>Malicious URL detected.</p>",
                    status_code=403,
                )

            # English: Block if "http" is found in query params or body.
            # Español: Bloquear si se encuentra "http" en los parámetros de consulta o el cuerpo.
            if "http" in query_params or "http" in str(body):
                self.blocked_ips[client_ip] = {
                    "expiration_time": (datetime.now() + timedelta(hours=6)).isoformat()
                }
                save_blocked_data(self.blocked_ips_file, self.blocked_ips)
                return HTMLResponse(
                    content="<h1>Access Denied</h1>",
                    status_code=403,
                )

            # English: Block sensitive paths in URLs or body content.
            # Español: Bloquear rutas sensibles en URLs o contenido del cuerpo.
            if any(
                path in url_path or path in str(body) for path in self.sensitive_paths
            ):
                self.blocked_ips[client_ip] = {
                    "expiration_time": (datetime.now() + timedelta(hours=6)).isoformat()
                }
                save_blocked_data(self.blocked_ips_file, self.blocked_ips)
                return HTMLResponse(
                    content="<h1>Access Denied</h1>",
                    status_code=403,
                )
            
           
            # English: If everything is fine, log the request and proceed.
            # Español: Si todo está bien, registrar la solicitud y continuar.
            Logger.info(await Logger.request(request=request))
            response = await call_next(request)
            return response

        except Exception as e:
            # English: Log the error and return a 500 response.
            # Español: Registrar el error y devolver una respuesta 500.
            Logger.error(f"Unhandled Error: {str(e)}")
            return JSONResponse(
                {"error": "Internal Server Error", "success": False}, status_code=500
            )
