from dotenv import load_dotenv
from os import getenv, path
import os

env_path = path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path, encoding="utf-8")
SECRET_KEY = getenv("SECRET_KEY", "")
PORT = int(getenv("PORT", 8001))
HOST = getenv("HOST", "127.0.0.1")
DEBUG = getenv("DEBUG", "True").lower() in ("true", "1", "yes")



PATH_LOG_BASE_DIR = "app/logs"
PATH_SECURITY = "app/security/"
PATH_TEMPLATE_NOT_FOUND = "templates/html/404.html"
PATH_TEMPLATES_HTML ="templates/html/"
PATH_TEMPLATES_MARKDOWN = "templates/markdown/"
PATH_LOCALES = "app/locales"
PATH_UPLOADS='/static/img/uploads'


#Project
TITLE_PROJECT = "Lila project"
VERSION_PROJECT = 1
DESCRIPTION_PROJECT = ""
THEME_DEFAULT = "blue"
LANG_DEFAULT = "en"
DESCRIPTION_DEFAULT = getenv("DESCRIPTION_DEFAULT", "A Python web framework")
KEYWORDS_DEFAULT = getenv("KEYWORDS_DEFAULT", "Python, web, framework")
AUTHOR_DEFAULT = getenv("AUTHOR_DEFAULT", "Seip")


#Security
SENSITIVE_PATHS = [
    "/admin",
    "/config",
    "/env",
    "/.env",
    "/.git",
    "/wp-admin",
    "/wp-login",
    "/database",
    "/backup",
]
