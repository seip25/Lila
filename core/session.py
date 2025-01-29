import json
from core.env import SECRET_KEY
from itsdangerous import Signer, BadSignature
from core.request import Request

signer = Signer(SECRET_KEY)

class Session:
    @staticmethod
    def setSession( new_val: str| dict | list, response,name_cookie:str="session",secure : bool=False) -> None:
        if isinstance(new_val, (dict, list)): 
            new_val = json.dumps(new_val)
        signed_session = signer.sign(new_val.encode("utf-8")) 
        response.set_cookie(name_cookie,
        value=signed_session.decode("utf-8"),
        httponly=True,
        secure=secure,
        samesite="Lax"
)
    @staticmethod
    def getSession( key: str, request: Request) -> dict | str | None:
        return request.cookies.get(key)
    
    @staticmethod
    def unsign( key: str, request: Request) -> dict | str | None:
        session_data = request.cookies.get(key)
        if not session_data:
            return None
        try:
            unsigned_data = signer.unsign(session_data).decode("utf-8")
            try:
                return json.loads(unsigned_data)
            except json.JSONDecodeError:
                return unsigned_data
        except BadSignature:
            return None
 