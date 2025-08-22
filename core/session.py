import json
from app.config import SECRET_KEY
from itsdangerous import BadSignature, URLSafeTimedSerializer,SignatureExpired
from core.request import Request
from typing import Any, Union, Optional, Dict, List
from core.logger import Logger

serializer = URLSafeTimedSerializer(SECRET_KEY)


class Session:
    @staticmethod
    def setSession(
        new_val: str | dict | list,
        response,
        name_cookie: str = "session",
        secure: bool = True,
        samesite: str = "strict",
        max_age: int = 3600,
        domain: Optional[str] = None,
        http_only: bool = True,
        path: str = "/",
    ) -> bool:
        try:
            if isinstance(new_val, (dict, list)):
                new_val = json.dumps(new_val)
            else:
                new_val = str(new_val)

            signed_session = serializer.dumps(new_val)

            response.set_cookie(
                key=name_cookie,
                value=signed_session,
                max_age=max_age,
                expires=max_age,
                secure=secure,
                httponly=http_only,
                samesite=samesite,
                domain=domain,
                path=path,
            )
            return True
        except (TypeError, ValueError, Exception) as e:
            Logger.error(f"Error setting session: {str(e)}")
            print(f"Error session {str(e)}")
            return False

    @staticmethod
    def getSession(key: str, request: Request) -> Optional[str]:
        return request.cookies.get(key)

    @staticmethod
    def unsign(
        key: str, request: Request, max_age: Optional[int] = None
    ) -> Union[Dict, List, str, None]:
        session_data = request.cookies.get(key)
        if not session_data:
            return None

        try:
            unsigned_data = serializer.loads(session_data, max_age=max_age)
            try:
                return json.loads(unsigned_data)
            except json.JSONDecodeError:
                return unsigned_data

        except BadSignature:
            msg = f"Invalid session signature for cookie: {key}"
            print(msg)
            Logger.warning(msg)
            return None
        except Exception as e:
            msg = f"Error unsigning session: {str(e)}"
            print(msg)
            Logger.error(msg)
            return None

    @staticmethod
    def deleteSession(response, name_cookie: str) -> bool:
        try:
            response.delete_cookie(name_cookie)
            return True
        except Exception as e:
            msg = f"Error deleting session: {str(e)}"
            print(e)
            Logger.error(msg)
            return False
        
    @staticmethod
    def getSessionValue(
         request: Request,key: str='auth', max_age: Optional[int] = 3600
    ) -> Union[Dict, List, str, None]:
        session_data = request.cookies.get(key)
        if not session_data:
            return None

        try:
            unsigned_data = serializer.loads(session_data, max_age=max_age)
            try:
                return json.loads(unsigned_data)
            except json.JSONDecodeError:
                return unsigned_data

        except BadSignature:
            msg = f"Invalid session signature for cookie: {key}"
            print(msg)
            Logger.warning(msg)
            return None
        except SignatureExpired:
            msg = f"Session expired for cookie: {key}"
            print(msg)
            Logger.warning(msg)
            return None
        except Exception as e:
            msg = f"Error unsigning session: {str(e)}"
            print(msg)
            Logger.error(msg)
            return None
