from app.helpers.helpers import LANG_DEFAULT
from core.session import Session
from core.request import Request

class Translate:
   
    def setLang(self,new_lang : str,response )-> None:
        lang ={'lang':new_lang}
        Session.setSession(new_lang=lang,response=response)
        
    def getLang(self,request : Request)->str :
        session_lang=Session.getSessionValue(key='lang',request=request)
        lang = session_lang if session_lang else LANG_DEFAULT
        return lang