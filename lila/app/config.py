"""
Application configuration for Lila Framework.
Framework variables (SECRET_KEY, DEBUG, PORT, etc.) are loaded
automatically from .env — edit .env to customize settings.
For custom user-defined variables, use:
  ENV_CONFIG["MY_VAR"] or ENV_CONFIG.get("MY_VAR", "default")
"""

import os
from os import path
from lila.core.config import ConfigLoader, ENV_CONFIG

_cfg = ConfigLoader.load()
globals().update(_cfg)

# Project paths
PATH_LOG_BASE_DIR = "app/logs"
PATH_TEMPLATE_NOT_FOUND = "lila/404"
PATH_TEMPLATES_HTML = "resources/html/"
PATH_TEMPLATES_MARKDOWN = "resources/markdown/"
PATH_LOCALES = "app/locales"
PATH_UPLOADS = path.join(os.getcwd(), "public", "img", "uploads")