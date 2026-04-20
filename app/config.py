from dotenv import load_dotenv
from os import getenv, path
import os

env_path = path.join(os.getcwd(), ".env")
load_dotenv(dotenv_path=env_path, encoding="utf-8")
SECRET_KEY = getenv("SECRET_KEY", "")
PORT = int(getenv("PORT", 8001))
HOST = getenv("HOST", "127.0.0.1")
DEBUG = getenv("DEBUG", "True").lower() in ("true", "1", "yes")
JIT=getenv("JIT", "True").lower() in ("true", "1", "yes")
WORKERS=int(getenv("WORKERS", "1"))


PATH_LOG_BASE_DIR = "app/logs"
PATH_TEMPLATE_NOT_FOUND = "lila/404"
PATH_TEMPLATES_HTML ="resources/templates/html/"
PATH_TEMPLATES_MARKDOWN = "resources/templates/markdown/"
PATH_LOCALES = "app/locales"
PATH_UPLOADS = path.join(os.getcwd(), "public", "img", "uploads")


#Project
TITLE_PROJECT = getenv("TITLE_PROJECT", "Lila project")
VERSION_PROJECT = getenv("VERSION_PROJECT", 1)
DESCRIPTION_PROJECT = getenv("DESCRIPTION_PROJECT", "") 
LANG_DEFAULT = getenv("LANG_DEFAULT", "en")
DESCRIPTION_DEFAULT = getenv("DESCRIPTION_DEFAULT", "A Python web framework")
KEYWORDS_DEFAULT = getenv("KEYWORDS_DEFAULT", "Python, web, framework")
AUTHOR_DEFAULT = getenv("AUTHOR_DEFAULT", "Seip")