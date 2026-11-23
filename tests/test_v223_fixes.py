import asyncio
import os
import socket
import sys
import threading
import time
import types as pytypes
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from starlette.testclient import TestClient

from lila.core import desktop as desktop_mod
from lila.core.app import App
from lila.core.config import ConfigLoader, server_graceful_timeout
from lila.core.request import Request
from lila.core.routing import Router
from lila.core.sse import Channel, EventStream, reset_shutdown, signal_shutdown


class _DummyReceive:
    async def __call__(self):
        return {"type": "http.disconnect"}


class _FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


class V223FixesTests(unittest.TestCase):
    def setUp(self):
        self._saved_desktop = os.environ.get("LILA_DESKTOP")
        self._saved_graceful = os.environ.get("LILA_GRACEFUL_TIMEOUT")
        self._saved_loaded = ConfigLoader._loaded
        self._saved_data = dict(ConfigLoader._data)
        self._saved_unavailable = list(desktop_mod._UNAVAILABLE)
        reset_shutdown()

    def tearDown(self):
        reset_shutdown()
        desktop_mod.register_unavailable(self._saved_unavailable)
        if self._saved_desktop is None:
            os.environ.pop("LILA_DESKTOP", None)
        else:
            os.environ["LILA_DESKTOP"] = self._saved_desktop
        if self._saved_graceful is None:
            os.environ.pop("LILA_GRACEFUL_TIMEOUT", None)
        else:
            os.environ["LILA_GRACEFUL_TIMEOUT"] = self._saved_graceful
        ConfigLoader._loaded = self._saved_loaded
        ConfigLoader._data = self._saved_data

    def test_sse_signal_shutdown_exits_event_stream_immediately(self):
        async def infinite_source():
            while True:
                yield {"event": "tick", "data": {"ok": True}}
                await asyncio.sleep(10)

        chunks = []

        async def run_stream():
            stream = EventStream(_FakeRequest(), infinite_source(), heartbeat=10.0)

            async def send(msg):
                if msg.get("type") == "http.response.body" and msg.get("body"):
                    chunks.append(msg["body"])

            task = asyncio.create_task(
                stream({"type": "http"}, _DummyReceive(), send)
            )
            await asyncio.sleep(0.05)
            signal_shutdown()
            await asyncio.wait_for(task, timeout=1.0)

        t0 = time.monotonic()
        asyncio.run(run_stream())
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 0.75)
        self.assertTrue(any(b"event: ready" in c for c in chunks))

    def test_live_uvicorn_shuts_down_with_open_sse_client(self):
        import uvicorn

        channel = Channel("v223_live_test")
        router = Router()

        @router.get("/sse")
        async def sse_endpoint(request: Request):
            return channel.stream(request, heartbeat=15.0)

        app = App(routes=[router], debug=False, health=False, openapi=False, csp=False)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            timeout_graceful_shutdown=1,
            log_config=None,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None

        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        client_sock = None
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if server.started:
                    break
                time.sleep(0.05)
            self.assertTrue(server.started, "Uvicorn did not start in time")

            client_sock = socket.create_connection(("127.0.0.1", port), timeout=3.0)
            client_sock.sendall(
                f"GET /sse HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: keep-alive\r\n\r\n".encode("ascii")
            )
            received = b""
            read_deadline = time.monotonic() + 3.0
            while time.monotonic() < read_deadline and b"event: ready" not in received:
                received += client_sock.recv(4096)
            self.assertIn(b"event: ready", received)

            # Trigger shutdown WITHOUT closing the client SSE socket
            t0 = time.monotonic()
            signal_shutdown()
            server.should_exit = True
            thread.join(timeout=4.0)
            elapsed = time.monotonic() - t0
            self.assertFalse(thread.is_alive(), "Uvicorn hung while SSE client socket remained open")
            self.assertLess(elapsed, 4.0)
        finally:
            signal_shutdown()
            server.should_exit = True
            if client_sock is not None:
                try:
                    client_sock.close()
                except Exception:
                    pass
            if thread.is_alive():
                thread.join(timeout=2.0)

    def test_future_annotations_route_with_pydantic_body_and_query(self):
        src = """
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from lila.core.routing import Router
from lila.core.request import Request

router = Router(prefix="/api")

class ItemIn(BaseModel):
    title: str = Field(..., min_length=2)
    qty: int = Field(1, ge=1)

@router.post("/items", model=ItemIn)
async def create_item(request: Request, data: ItemIn):
    return {"title": data.title, "qty": data.qty}

@router.get("/items/{id:int}")
async def get_item(request: Request, id: int, q: Optional[str] = None):
    return {"id": id, "q": q}
"""
        mod = pytypes.ModuleType("v223_future_routes")
        exec(compile(src, "<v223_future_routes>", "exec"), mod.__dict__)
        app = App(routes=[mod.router], debug=False, openapi=False, csp=False)

        with TestClient(app) as client:
            ok = client.post("/api/items", json={"title": "Notebook", "qty": 3})
            self.assertEqual(ok.status_code, 200, ok.text)
            self.assertEqual(ok.json(), {"title": "Notebook", "qty": 3})

            bad = client.post("/api/items", json={"title": "A", "qty": 0})
            self.assertEqual(bad.status_code, 422, bad.text)
            self.assertNotIn("data: Field required", bad.text)

            qres = client.get("/api/items/42")
            self.assertEqual(qres.status_code, 200)
            self.assertEqual(qres.json(), {"id": 42, "q": None})

    def test_dual_target_same_path_keeps_route_available(self):
        router = Router()

        @router.get("/", desktop=False)
        async def web_root(request: Request):
            return {"target": "web"}

        @router.get("/", desktop="only")
        async def desktop_root(request: Request):
            return {"target": "desktop"}

        os.environ["LILA_DESKTOP"] = "0"
        web_app = App(routes=[router], debug=False, openapi=False, csp=False)
        with TestClient(web_app) as client:
            self.assertEqual(client.get("/").json(), {"target": "web"})
            self.assertTrue(desktop_mod.route_available("/"))

        os.environ["LILA_DESKTOP"] = "1"
        desk_app = App(routes=[router], debug=False, openapi=False, csp=False)
        with TestClient(desk_app) as client:
            self.assertEqual(client.get("/").json(), {"target": "desktop"})
            self.assertTrue(desktop_mod.route_available("/"))

    def test_cli_run_and_config_graceful_timeout(self):
        from lila.cli import main as cli_main

        os.environ.pop("LILA_GRACEFUL_TIMEOUT", None)
        ConfigLoader._loaded = True
        ConfigLoader._data = {
            "DEBUG": False,
            "HOST": "127.0.0.1",
            "PORT": 8000,
            "CACHE_DRIVER": "memory",
            "LILA_SERVER": "uvicorn",
            "LILA_ACCESS_LOG": False,
            "LILA_LOG_LEVEL": "",
            "LILA_GRACEFUL_TIMEOUT": 7,
        }
        self.assertEqual(server_graceful_timeout(), 7)
        self.assertEqual(server_graceful_timeout(3), 3)

        captured = {}

        def fake_run(app_str, **kwargs):
            captured.update(kwargs)

        with patch("os.path.exists", return_value=True), patch.dict(
            sys.modules, {"uvicorn": SimpleNamespace(run=fake_run)}
        ):
            cli_main.run(
                host="127.0.0.1",
                port=8000,
                workers=1,
                proxy_headers=True,
                forwarded_allow_ips="127.0.0.1",
                server="uvicorn",
                max_rss=0,
                access_log=None,
                log_level="",
                graceful_timeout=None,
            )
        self.assertEqual(captured["timeout_graceful_shutdown"], 7)


if __name__ == "__main__":
    unittest.main()
