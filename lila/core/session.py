import orjson
import secrets
from app.config import SECRET_KEY
from itsdangerous import BadSignature, URLSafeTimedSerializer, SignatureExpired
from lila.core.request import Request
from typing import Union, Optional, Dict, List
from lila.core.logger import Logger
from lila.core.cache import _REDIS_CLIENT

serializer = URLSafeTimedSerializer(SECRET_KEY)


class Session:
    """
    English: Session manager supporting Redis storage with a secure fallback to client-side cookie serialization.
    """
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
                serialized_val = orjson.dumps(new_val).decode()
            else:
                serialized_val = str(new_val)

            if _REDIS_CLIENT is not None:
                session_id = secrets.token_urlsafe(32)
                _REDIS_CLIENT.setex(
                    name=f"lila:session:{session_id}",
                    time=max_age,
                    value=serialized_val
                )
                cookie_value = f"sid:{session_id}"
            else:
                cookie_value = serialized_val

            signed_session = serializer.dumps(cookie_value)

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
        except Exception as e:
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

            if isinstance(unsigned_data, str) and unsigned_data.startswith("sid:"):
                session_id = unsigned_data[4:]
                if _REDIS_CLIENT is not None:
                    cached_val = _REDIS_CLIENT.get(f"lila:session:{session_id}")
                    if cached_val is not None:
                        decoded_val = cached_val.decode("utf-8")
                        try:
                            return orjson.loads(decoded_val)
                        except orjson.JSONDecodeError:
                            return decoded_val
                return None

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
    def deleteSession(response, name_cookie: str, request: Optional[Request] = None) -> bool:
        try:
            if request and _REDIS_CLIENT is not None:
                cookie_val = request.cookies.get(name_cookie)
                if cookie_val:
                    try:
                        unsigned_data = serializer.loads(cookie_val)
                        if isinstance(unsigned_data, str) and unsigned_data.startswith("sid:"):
                            session_id = unsigned_data[4:]
                            _REDIS_CLIENT.delete(f"lila:session:{session_id}")
                    except Exception:
                        pass
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
    async def delete(response, key: str = "auth", request: Optional[Request] = None) -> bool:
        """Async helper to delete session data."""
        return Session.deleteSession(response=response, name_cookie=key, request=request)

    @staticmethod
    def flash(request: Request, message: str, category: str = "info") -> None:
        """
        English: Queues a flash message to be shown on the next request.
        """
        if not hasattr(request.state, "_new_flashes"):
            request.state._new_flashes = []
        request.state._new_flashes.append({"message": message, "category": category})


def flash(request: Request, message: str, category: str = "info") -> None:
    """
    English: Queues a flash message to be shown on the next request.
    """
    Session.flash(request, message, category)


