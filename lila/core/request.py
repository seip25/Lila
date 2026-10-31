"""Lila Request Object.

Lila handlers receive Starlette's real ``Request`` instance. Re-exporting the
same class (instead of a subclass) keeps ``isinstance()`` checks in decorators,
middlewares and user code compatible.
"""

from starlette.requests import Request

__all__ = ["Request"]
