"""Lila Framework v2.0.x

High-performance full-stack Python web framework with SPA View Transitions,
Zero-Infra SQLite WAL, In-Memory/Redis/File cache, AI helper, and Desktop mode.

Imports are lazy (PEP 562): ``import lila`` stays lightweight, while
``from lila import App, Router, Cache`` keeps working exactly as before.
"""

__version__ = "2.0.1"

_LAZY_ATTRS = {
    "App": ("lila.core.app", "App"),
    "Router": ("lila.core.routing", "Router"),
    "Cache": ("lila.core.cache", "Cache"),
    "cached": ("lila.core.cache", "cached"),
    "Database": ("lila.core.database", "Database"),
    "db": ("lila.core.database", "db"),
    "BaseModel": ("lila.core.base_model", "BaseModel"),
    "Request": ("lila.core.request", "Request"),
    "JSONResponse": ("lila.core.responses", "JSONResponse"),
    "HTMLResponse": ("lila.core.responses", "HTMLResponse"),
    "RedirectResponse": ("lila.core.responses", "RedirectResponse"),
    "StreamingResponse": ("lila.core.responses", "StreamingResponse"),
    "PlainTextResponse": ("lila.core.responses", "PlainTextResponse"),
    "FileResponse": ("lila.core.responses", "FileResponse"),
    "IA": ("lila.core.ia", "IA"),
    "WebSocketHub": ("lila.core.websocket", "WebSocketHub"),
    "ws": ("lila.core.websocket", "ws"),
    "OAuth": ("lila.core.oauth", "OAuth"),
    "Session": ("lila.core.session", "Session"),
    "JWT": ("lila.core.auth", "JWT"),
    "PasswordHasher": ("lila.core.auth", "PasswordHasher"),
    "TOTP": ("lila.core.two_factor", "TOTP"),
    "Translate": ("lila.core.translate", "Translate"),
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module 'lila' has no attribute '{name}'")
    module_name, attr_name = target
    import importlib

    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(_LAZY_ATTRS.keys()))


__all__ = [
    "__version__",
    *sorted(_LAZY_ATTRS.keys()),
]
