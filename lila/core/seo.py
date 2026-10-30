"""SEO helpers for Lila.

Usage::

    from lila.core.routing import seo

    @router.get("/")
    @seo(title="Home", description="Welcome", canonical="https://example.com/")
    async def home(request): ...

    # Or centrally:
    SEO_CONFIG = {"/": {"title": "Home", "description": "..."}}
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional

SEO_CONFIG: Dict[str, dict] = {}


def _request_from(args, kwargs):
    req = kwargs.get("request")
    if req is not None:
        return req
    for arg in args:
        if hasattr(arg, "url") and hasattr(arg, "headers"):
            return arg
    return None


def seo(**metadata):
    """Decorator injecting ``request.state.seo`` and the template ``seo`` object."""

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            request = _request_from(args, kwargs)
            merged: Dict[str, Any] = {}
            if request is not None:
                try:
                    path = request.url.path
                    merged.update(SEO_CONFIG.get(path, {}))
                except Exception:
                    pass
            merged.update(metadata)
            if request is not None:
                # Resolve per-language dictionaries at request time.
                try:
                    from lila.core.translate import Translate

                    lang = Translate.lang(request)
                    for key, value in list(merged.items()):
                        if isinstance(value, dict):
                            merged[key] = value.get(lang) or value.get("en") or next(iter(value.values()), "")
                except Exception:
                    pass
                request.state.seo = merged
            result = fn(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result
            return result

        return wrapper

    return decorator
