from app.config import  LANG_DEFAULT, PATH_LOCALES
from core.session import Session
from core.request import Request 
import json
from pathlib import Path 

_TRANSLATIONS_CACHE: dict[str, dict] = {}

def load_translations(file_name: str) -> dict:
    if file_name in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[file_name]

    file_path = Path(PATH_LOCALES) / f"{file_name}.json"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _TRANSLATIONS_CACHE[file_name] = data 
        return data
    except Exception:
        _TRANSLATIONS_CACHE[file_name] = {}
        return {}

def lang(request: Request) -> str:
    l = LANG_DEFAULT or "en"
    session_lang = Session.getSessionValue(key="lang", request=request) 
    if session_lang:
        l = Session.unsign(key="lang", request=request) 
    return l

def translate(file_name: str, request: Request, lang_default: str = None) -> dict:
    current_lang = lang(request) if not lang_default else lang_default
    data = load_translations(file_name)
    translations = {k: v.get(current_lang, k) for k, v in data.items()}
    return translations


def translate_(
    key: str,
    request: Request,
    file_name: str = "translations",
    lang_default: str = None,
) -> str:
    t = translate(file_name=file_name, request=request, lang_default=lang_default)
    if key in t:
        msg = t[key]
        return msg if msg not in [None, ""] else key
    return key
