"""ASGI entry used by ``lila run --server granian``.

Granian has no ``--proxy-headers`` option, so Lila wraps ``main:app`` with
Uvicorn's ProxyHeadersMiddleware, trusting only ``LILA_FORWARDED_ALLOW_IPS``
(127.0.0.1 by default: a local Nginx).
"""

import importlib
import os
import sys

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

_main = importlib.import_module(os.environ.get("LILA_APP_MODULE", "main"))
_app = getattr(_main, os.environ.get("LILA_APP_ATTR", "app"))

if os.environ.get("LILA_PROXY_HEADERS", "1") == "1":
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app = ProxyHeadersMiddleware(_app, trusted_hosts=os.environ.get("LILA_FORWARDED_ALLOW_IPS", "127.0.0.1"))
else:
    app = _app
