"""Lila Request Object.
Re-exports Starlette Request with Lila extensions and __slots__.
"""

from starlette.requests import Request as StarletteRequest


class Request(StarletteRequest):
    __slots__ = ("_user_cache",)
