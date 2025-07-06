from dotenv import load_dotenv
from os import getenv, path
import os

env_path = path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=env_path, encoding='utf-8')

TITLE_PROJECT = getenv('TITLE_PROJECT', 'title project')
VERSION_PROJECT = getenv('VERSION_PROJECT', 1)  
DESCRIPTION_PROJECT = getenv('DESCRIPTION_PROJECT', '')
THEME_DEFAULT = getenv('THEME_DEFAULT', 'blue')
LANG_DEFAULT = getenv('LANG_DEFAULT', 'en')
SECRET_KEY = getenv('SECRET_KEY', '')
PORT = int(getenv('PORT', 8001))  
HOST = getenv('HOST', '127.0.0.1')
DEBUG = getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')