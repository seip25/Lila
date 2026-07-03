"""
English: Application configuration for the Lila Framework.
         Framework variables (SECRET_KEY, DEBUG, PORT, etc.) are loaded
         automatically from .env — just edit .env and they're available.
         For custom variables not built into the framework, use:
           ENV_CONFIG["MY_VAR"] or ENV_CONFIG.get("MY_VAR", "default")
Español: Configuración de la aplicación para el Lila Framework.
         Las variables del framework (SECRET_KEY, DEBUG, PORT, etc.) se cargan
         automáticamente desde .env — solo edita .env y están disponibles.
         Para variables custom que no son del framework, usar:
           ENV_CONFIG["MI_VAR"] o ENV_CONFIG.get("MI_VAR", "default")
"""

import os
from os import path
from lila.core.config import ConfigLoader, ENV_CONFIG

_cfg = ConfigLoader.load()
globals().update(_cfg)

# English: Project-specific paths (not loaded from .env).
# Español: Rutas específicas del proyecto (no se cargan desde .env).
PATH_LOG_BASE_DIR = "app/logs"
PATH_TEMPLATE_NOT_FOUND = "lila/404"
PATH_TEMPLATES_HTML = "resources/html/"
PATH_TEMPLATES_MARKDOWN = "resources/markdown/"
PATH_LOCALES = "app/locales"
PATH_UPLOADS = path.join(os.getcwd(), "public", "img", "uploads") 
#English: example ENV_CONFIG.get("API_KEY", "default") -> "your_api_key"
#Español: ejemplo ENV_CONFIG.get("API_KEY", "default") -> "tu_clave_api"