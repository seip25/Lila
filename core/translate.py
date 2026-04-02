from app.helpers.translate import lang
from app.config import LANG_DEFAULT
from lila.core.session import Session
from lila.core.request import Request


class Translate:

    def setLang(self, new_lang: str, response) -> None:
        Session.setSession(new_val=new_lang, response=response, name_cookie="lang")

    def getLang(self, request: Request) -> str:
        session_lang = Session.getSessionValue(key="lang", request=request)
        return session_lang if session_lang else LANG_DEFAULT