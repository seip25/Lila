import orjson
import secrets
from app.config import SECRET_KEY
from itsdangerous import BadSignature, URLSafeTimedSerializer, SignatureExpired
from lila.core.request import Request
from typing import Union, Optional, Dict, List
from lila.core.logger import Logger
from lila.core.cache import _get_redis_client, _get_redis_client_async

serializer = URLSafeTimedSerializer(SECRET_KEY)


class Session:
    """Session manager supporting Redis storage with secure fallback to cookies."""

    @staticmethod
    def setSession(
        new_val: Union[str, dict, list],
        response,
        name_cookie: str = "session",
        secure: bool = True,
        samesite: str = "strict",
        max_age: int = 3600,
        domain: Optional[str] = None,
        http_only: bool = True,
        path: str = "/",
    ) -> bool:
        """Set session data synchronously."""
        try:
            if isinstance(new_val, (dict, list)):
                serialized_val = orjson.dumps(new_val).decode()
            else:
                serialized_val = str(new_val)

            client = _get_redis_client()
            if client is not None:
                session_id = secrets.token_urlsafe(32)
                client.setex(
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
    async def setSession_async(
        new_val: Union[str, dict, list],
        response,
        name_cookie: str = "session",
        secure: bool = True,
        samesite: str = "strict",
        max_age: int = 3600,
        domain: Optional[str] = None,
        http_only: bool = True,
        path: str = "/",
    ) -> bool:
        """Set session data asynchronously."""
        try:
            if isinstance(new_val, (dict, list)):
                serialized_val = orjson.dumps(new_val).decode()
            else:
                serialized_val = str(new_val)

            client_async = await _get_redis_client_async()
            if client_async is not None:
                session_id = secrets.token_urlsafe(32)
                await client_async.setex(
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
        """Retrieve request cookie session value."""
        return request.cookies.get(key)

    @staticmethod
    def unsign(
        key: str, request: Request, max_age: Optional[int] = None
    ) -> Union[Dict, List, str, None]:
        """Unsign and return session data synchronously."""
        session_data = request.cookies.get(key)
        if not session_data:
            return None

        try:
            unsigned_data = serializer.loads(session_data, max_age=max_age)

            if isinstance(unsigned_data, str) and unsigned_data.startswith("sid:"):
                session_id = unsigned_data[4:]
                client = _get_redis_client()
                if client is not None:
                    cached_val = client.get(f"lila:session:{session_id}")
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
    async def unsign_async(
        key: str, request: Request, max_age: Optional[int] = None
    ) -> Union[Dict, List, str, None]:
        """Unsign and return session data asynchronously."""
        session_data = request.cookies.get(key)
        if not session_data:
            return None

        try:
            unsigned_data = serializer.loads(session_data, max_age=max_age)

            if isinstance(unsigned_data, str) and unsigned_data.startswith("sid:"):
                session_id = unsigned_data[4:]
                client_async = await _get_redis_client_async()
                if client_async is not None:
                    cached_val = await client_async.get(f"lila:session:{session_id}")
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
        """Delete session synchronously."""
        try:
            if request:
                client = _get_redis_client()
                if client is not None:
                    cookie_val = request.cookies.get(name_cookie)
                    if cookie_val:
                        try:
                            unsigned_data = serializer.loads(cookie_val)
                            if isinstance(unsigned_data, str) and unsigned_data.startswith("sid:"):
                                session_id = unsigned_data[4:]
                                client.delete(f"lila:session:{session_id}")
                        except Exception:
                            pass
            response.delete_cookie(name_cookie)
            return True
        except Exception as e:
            Logger.error(f"Error deleting session: {str(e)}")
            return False

    @staticmethod
    async def deleteSession_async(response, name_cookie: str, request: Optional[Request] = None) -> bool:
        """Delete session asynchronously."""
        try:
            if request:
                client_async = await _get_redis_client_async()
                if client_async is not None:
                    cookie_val = request.cookies.get(name_cookie)
                    if cookie_val:
                        try:
                            unsigned_data = serializer.loads(cookie_val)
                            if isinstance(unsigned_data, str) and unsigned_data.startswith("sid:"):
                                session_id = unsigned_data[4:]
                                await client_async.delete(f"lila:session:{session_id}")
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
        """Get session value synchronously."""
        return Session.unsign(key=key, request=request, max_age=max_age)

    @staticmethod
    async def get(request: Request, key: str = "auth") -> Union[Dict, List, str, None]:
        """Get session data asynchronously."""
        return await Session.unsign_async(key=key, request=request)

    @staticmethod
    async def set(
        request: Request, response, data: dict, key: str = "auth", max_age: int = 3600
    ) -> bool:
        """Set session data asynchronously."""
        return await Session.setSession_async(new_val=data, response=response, name_cookie=key, max_age=max_age)

    @staticmethod
    async def delete(response, key: str = "auth", request: Optional[Request] = None) -> bool:
        """Delete session data asynchronously."""
        return await Session.deleteSession_async(response=response, name_cookie=key, request=request)

    @staticmethod
    def flash(request: Request, message: str, category: str = "info") -> None:
        """Queue a flash message."""
        if not hasattr(request.state, "_new_flashes"):
            request.state._new_flashes = []
        request.state._new_flashes.append({"message": message, "category": category})


def flash(request: Request, message: str, category: str = "info") -> None:
    """Queue a flash message."""
    Session.flash(request, message, category)
