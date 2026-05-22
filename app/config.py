"""
English: Configuration Loader for the Lila Framework.
Español: Cargador de configuración para el Lila Framework.
"""

import os
from os import getenv, path

def _load_config() -> dict:
    """
    English: Loads the configuration dictionary from cache if available and DEBUG is False, otherwise loads from env.
    Español: Carga el diccionario de configuración desde la caché si está disponible y DEBUG es False, de lo contrario lo carga desde env.
    """
    cache_py_path = path.join(path.dirname(__file__), "config_cache.py")
    env_path = path.join(os.getcwd(), ".env")
    
    env_debug = os.environ.get("DEBUG")
    if env_debug is not None and env_debug.lower() in ("true", "1", "yes"):
        return _read_from_env(cache_py_path, write_cache=False)
        
    if path.exists(cache_py_path):
        env_modified = path.exists(env_path) and os.path.getmtime(env_path) > os.path.getmtime(cache_py_path)
        if not env_modified:
            try:
                from app import config_cache
                if hasattr(config_cache, "DEBUG") and not config_cache.DEBUG:
                    return {
                        "SECRET_KEY": config_cache.SECRET_KEY,
                        "PORT": config_cache.PORT,
                        "HOST": config_cache.HOST,
                        "DEBUG": config_cache.DEBUG,
                        "JIT": config_cache.JIT,
                        "WORKERS": config_cache.WORKERS,
                        "TITLE_PROJECT": config_cache.TITLE_PROJECT,
                        "VERSION_PROJECT": config_cache.VERSION_PROJECT,
                        "DESCRIPTION_PROJECT": config_cache.DESCRIPTION_PROJECT,
                        "LANG_DEFAULT": config_cache.LANG_DEFAULT,
                        "DESCRIPTION_DEFAULT": config_cache.DESCRIPTION_DEFAULT,
                        "KEYWORDS_DEFAULT": config_cache.KEYWORDS_DEFAULT,
                        "AUTHOR_DEFAULT": config_cache.AUTHOR_DEFAULT,
                        "MINIFY_HTML": getattr(config_cache, "MINIFY_HTML", False),
                    }
            except ImportError:
                pass
                
    return _read_from_env(cache_py_path, write_cache=True)

def _read_from_env(cache_py_path: str, write_cache: bool) -> dict:
    """
    English: Reads the configuration values from the environment and optionally caches them.
    Español: Lee los valores de configuración desde el entorno y opcionalmente los almacena en caché.
    """
    from dotenv import load_dotenv
    env_path = path.join(os.getcwd(), ".env")
    if path.exists(env_path):
        load_dotenv(dotenv_path=env_path, encoding="utf-8")
        
    data = {
        "SECRET_KEY": getenv("SECRET_KEY", ""),
        "PORT": int(getenv("PORT", 8001)),
        "HOST": getenv("HOST", "127.0.0.1"),
        "DEBUG": getenv("DEBUG", "True").lower() in ("true", "1", "yes"),
        "JIT": getenv("JIT", "True").lower() in ("true", "1", "yes"),
        "WORKERS": int(getenv("WORKERS", "1")),
        "TITLE_PROJECT": getenv("TITLE_PROJECT", "Lila project"),
        "VERSION_PROJECT": getenv("VERSION_PROJECT", 1),
        "DESCRIPTION_PROJECT": getenv("DESCRIPTION_PROJECT", ""),
        "LANG_DEFAULT": getenv("LANG_DEFAULT", "en"),
        "DESCRIPTION_DEFAULT": getenv("DESCRIPTION_DEFAULT", "A Python web framework"),
        "KEYWORDS_DEFAULT": getenv("KEYWORDS_DEFAULT", "Python, web, framework"),
        "AUTHOR_DEFAULT": getenv("AUTHOR_DEFAULT", "Seip"),
        "MINIFY_HTML": getenv("MINIFY_HTML", "False").lower() in ("true", "1", "yes"),
    }
    
    if write_cache and not data["DEBUG"]:
        try:
            with open(cache_py_path, "w", encoding="utf-8") as f:
                f.write(f'SECRET_KEY = {repr(data["SECRET_KEY"])}\n')
                f.write(f'PORT = {repr(data["PORT"])}\n')
                f.write(f'HOST = {repr(data["HOST"])}\n')
                f.write(f'DEBUG = {repr(data["DEBUG"])}\n')
                f.write(f'JIT = {repr(data["JIT"])}\n')
                f.write(f'WORKERS = {repr(data["WORKERS"])}\n')
                f.write(f'TITLE_PROJECT = {repr(data["TITLE_PROJECT"])}\n')
                f.write(f'VERSION_PROJECT = {repr(data["VERSION_PROJECT"])}\n')
                f.write(f'DESCRIPTION_PROJECT = {repr(data["DESCRIPTION_PROJECT"])}\n')
                f.write(f'LANG_DEFAULT = {repr(data["LANG_DEFAULT"])}\n')
                f.write(f'DESCRIPTION_DEFAULT = {repr(data["DESCRIPTION_DEFAULT"])}\n')
                f.write(f'KEYWORDS_DEFAULT = {repr(data["KEYWORDS_DEFAULT"])}\n')
                f.write(f'AUTHOR_DEFAULT = {repr(data["AUTHOR_DEFAULT"])}\n')
                f.write(f'MINIFY_HTML = {repr(data["MINIFY_HTML"])}\n')
        except Exception:
            pass
            
    return data

_config = _load_config()

SECRET_KEY = _config["SECRET_KEY"]
PORT = _config["PORT"]
HOST = _config["HOST"]
DEBUG = _config["DEBUG"]
JIT = _config["JIT"]
WORKERS = _config["WORKERS"]
MINIFY_HTML = _config["MINIFY_HTML"]

PATH_LOG_BASE_DIR = "app/logs"
PATH_TEMPLATE_NOT_FOUND = "lila/404"
PATH_TEMPLATES_HTML = "resources/html/"
PATH_TEMPLATES_MARKDOWN = "resources/markdown/"
PATH_LOCALES = "app/locales"
PATH_UPLOADS = path.join(os.getcwd(), "public", "img", "uploads")

TITLE_PROJECT = _config["TITLE_PROJECT"]
VERSION_PROJECT = _config["VERSION_PROJECT"]
DESCRIPTION_PROJECT = _config["DESCRIPTION_PROJECT"]
LANG_DEFAULT = _config["LANG_DEFAULT"]
DESCRIPTION_DEFAULT = _config["DESCRIPTION_DEFAULT"]
KEYWORDS_DEFAULT = _config["KEYWORDS_DEFAULT"]
AUTHOR_DEFAULT = _config["AUTHOR_DEFAULT"]