from lila.core.session import Session
from lila.core.request import Request


async def get_session(request: Request, key: str='auth'):
    session_data = Session.unsign(key=key, request=request)
    return session_data


async def set_session(request: Request, data: dict, key: str='auth'):
    session_data = Session.sign(data=data, key=key, request=request)
    return session_data


async def delete_session(request: Request, key: str='auth'):
    session_data = Session.unsign(key=key, request=request)
    return session_data
