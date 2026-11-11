"""Helpers for testing Lila projects (unittest or pytest).

    from lila.testing import TestClient, login, csrf_headers, temp_database, override_env

    client = TestClient()                      # imports main:app
    login(client, {"id": 1, "email": "a@b.c", "role": "admin"})
    res = client.post("/api/items", json={"name": "x"}, headers=csrf_headers(client))

    async with temp_database(Product, Order) as db:   # throwaway SQLite, tables created
        await Product.insert_async(name="x")

    with override_env(DEBUG="False", CACHE_DRIVER="memory"):
        ...
"""

from __future__ import annotations

import importlib
import os
import secrets
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional

from starlette.testclient import TestClient as _StarletteTestClient


def _load_main_app():
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    return importlib.import_module("main").app


class TestClient(_StarletteTestClient):
    """Starlette TestClient that defaults to ``main:app`` and never raises
    server exceptions unless asked (so you can assert on 500 pages too)."""

    __test__ = False  # not a pytest test class

    def __init__(self, app: Any = None, raise_server_exceptions: bool = False, **kwargs):
        super().__init__(app or _load_main_app(), raise_server_exceptions=raise_server_exceptions, **kwargs)


def login(client, user: Dict[str, Any], cookie: str = "auth", max_age: int = 86400) -> None:
    """Signs a session cookie exactly like ``Session.set`` (passwords stripped)."""
    from lila.core.session import _envelope, _get_session_serializer, _serialize_payload

    value = _get_session_serializer().dumps(_envelope(_serialize_payload(user), max_age))
    client.cookies.set(cookie, value)


def logout(client, cookie: str = "auth") -> None:
    client.cookies.delete(cookie)


def csrf_headers(client) -> Dict[str, str]:
    """Sets a valid signed ``_csrf`` cookie and returns the matching header."""
    from lila.core.csrf import CSRF, CSRF_COOKIE_NAME

    token = secrets.token_urlsafe(16)
    client.cookies.set(CSRF_COOKIE_NAME, CSRF.sign(token))
    return {"X-CSRF-Token": token}


@asynccontextmanager
async def temp_database(*models, connection_attr: str = "_connection"):
    """Throwaway SQLite database; the given models use it inside the block."""
    from lila.core.database import Database

    folder = tempfile.mkdtemp(prefix="lila-test-")
    db = Database(config={"type": "sqlite", "database": os.path.join(folder, "test"), "is_async": True})
    db.connect()
    previous = {model: model.__dict__.get(connection_attr) for model in models}
    for model in models:
        setattr(model, connection_attr, db)
    try:
        tables = [m.__table__ for m in models] or None
        from lila.core.database import Base

        async with db.engine.begin() as conn:
            await conn.run_sync(lambda sc: Base.metadata.create_all(sc, tables=tables))
        yield db
    finally:
        for model, value in previous.items():
            if value is None:
                try:
                    delattr(model, connection_attr)
                except AttributeError:
                    setattr(model, connection_attr, None)
            else:
                setattr(model, connection_attr, value)
        await db.close_async()
        shutil.rmtree(folder, ignore_errors=True)


@contextmanager
def override_env(**values: Optional[str]):
    """Temporarily sets environment variables and the typed ENV_CONFIG values."""
    from lila.core.config import ConfigLoader, FRAMEWORK_SCHEMA, _cast_value

    types = {key: t for key, t, _ in FRAMEWORK_SCHEMA}
    old_env = {k: os.environ.get(k) for k in values}
    old_data = {k: ConfigLoader._data.get(k, _MISSING) for k in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
                ConfigLoader._data.pop(key, None)
            else:
                os.environ[key] = str(value)
                if ConfigLoader._loaded and key in types:
                    ConfigLoader._data[key] = _cast_value(str(value), types[key])
        yield
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key, value in old_data.items():
            if value is _MISSING:
                ConfigLoader._data.pop(key, None)
            else:
                ConfigLoader._data[key] = value


_MISSING = object()
