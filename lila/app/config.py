"""
Lila Framework Application Configuration.
Framework variables (SECRET_KEY, DEBUG, PORT, CACHE_DRIVER, etc.) are loaded automatically from .env.
"""

import os
from os import path
from lila.core.config import ConfigLoader, ENV_CONFIG

_cfg = ConfigLoader.load()
globals().update(_cfg)

PATH_LOG_BASE_DIR = "app/logs"
PATH_TEMPLATE_NOT_FOUND = "lila/404"
PATH_TEMPLATES_HTML = "resources/html/"
PATH_TEMPLATES_MARKDOWN = "resources/markdown/"
PATH_UPLOADS = path.join(os.getcwd(), "public", "img", "uploads")
