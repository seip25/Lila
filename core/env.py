from dotenv import load_dotenv
from os import getenv,path

BASE_DIR = path.abspath(path.dirname(__file__))
BASE_DIR = path.dirname(BASE_DIR) 
env =path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env,encoding='utf-8')

TITLE_PROJECT = getenv('TITLE_PROJECT', 'title project')
VERSION_PROJECT = getenv('VERSION_PROJECT', 1)  
DESCRIPTION_PROJECT = getenv('DESCRIPTION_PROJECT', '')
THEME_DEFAULT = getenv('THEME_DEFAULT', 'blue')
LANG_DEFAULT = getenv('LANG_DEFAULT', 'en')
SECRET_KEY = getenv('SECRET_KEY', '')
PORT = int(getenv('PORT', 8001))  
HOST = getenv('HOST', '127.0.0.1') 
DEBUG = getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')