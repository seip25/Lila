import orjson
from app.config import SECRET_KEY
from itsdangerous import BadSignature, URLSafeTimedSerializer, SignatureExpired
from lila.core.request import Request
from typing import Union, Optional, Dict, List
from lila.core.logger import Logger

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
                new_val = orjson.dumps(new_val).decode()
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
            return False

    @staticmethod
    def getSession(key: str, request: Request) -> Optional[str]:
        return request.cookies.get(key)

    @staticmethod
    def unsign(
        key: str, request: Request, max_age: Optional[int] = None
    ) -> Union[Dict, List, str, None]:
        """Unsign and return the session data for the given cookie key."""
        session_data = request.cookies.get(key)
        if not session_data:
            return None

        try:
            unsigned_data = serializer.loads(session_data, max_age=max_age)
            try:
                return orjson.loads(unsigned_data)
            except orjson.JSONDecodeError:
                return unsigned_data

        except SignatureExpired:
            Logger.warning(f"Session expired for cookie: {key}")
            return None
        except BadSignature:
            Logger.warning(f"Invalid session signature for cookie: {key}")
            return None
        except Exception as e:
            Logger.error(f"Error unsigning session: {str(e)}")
            return None

    @staticmethod
    def deleteSession(response, name_cookie: str) -> bool:
        try:
            response.delete_cookie(name_cookie)
            return True
        except Exception as e:
            Logger.error(f"Error deleting session: {str(e)}")
            return False

    @staticmethod
    def getSessionValue(
        request: Request, key: str = "auth", max_age: Optional[int] = 3600
    ) -> Union[Dict, List, str, None]:
        """Convenience wrapper around unsign with a default max_age."""
        return Session.unsign(key=key, request=request, max_age=max_age)

    @staticmethod
    async def get(request: Request, key: str = "auth") -> Union[Dict, List, str, None]:
        """Async helper to get session data."""
        return Session.unsign(key=key, request=request)

    @staticmethod
    async def set(
        request: Request, response, data: dict, key: str = "auth", max_age: int = 3600
    ) -> bool:
        """Async helper to set session data."""
        return Session.setSession(new_val=data, response=response, name_cookie=key, max_age=max_age)

    @staticmethod
    async def delete(response, key: str = "auth") -> bool:
        """Async helper to delete session data."""
        return Session.deleteSession(response=response, name_cookie=key)
