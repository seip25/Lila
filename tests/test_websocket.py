import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.routing import Router
from lila.core.websocket import WebSocketHub


class WebSocketHubTests(unittest.TestCase):
    def setUp(self):
        self.hub = WebSocketHub()
        self.disconnects = 0

        @self.hub.on_disconnect
        def _gone(ws):
            self.disconnects += 1

        @self.hub.can_join
        def _guard(ws, room):
            return not room.startswith("private:")

        @self.hub.on("echo")
        async def _echo(ws, data):
            await self.hub.emit(ws, "echo", data)

        router = Router()
        router.ws_hub("/ws", self.hub)
        self.client = TestClient(App(routes=[router], debug=False, rate_limit=None))

    def test_ping_echo_and_join_guard(self):
        with self.client.websocket_connect("/ws") as ws:
            ws.send_text('{"event": "ping"}')
            self.assertEqual(ws.receive_json(), {"event": "pong"})
            ws.send_text('{"event": "echo", "data": {"a": 1}}')
            self.assertEqual(ws.receive_json()["data"], {"a": 1})
            ws.send_text('{"event": "join", "data": "private:42"}')
            self.assertEqual(ws.receive_json()["event"], "join:denied")
            ws.send_text('{"event": "join", "data": "lobby"}')
            ws.send_text('{"event": "ping"}')
            ws.receive_json()
            self.assertIn("lobby", self.hub.rooms)
            self.assertNotIn("private:42", self.hub.rooms)
        self.assertEqual(self.disconnects, 1)
        self.assertEqual(self.hub.rooms, {})

    def test_disconnect_is_idempotent(self):
        class FakeWS:
            pass

        fake = FakeWS()
        self.hub.active_connections.add(fake)
        self.hub.client_rooms[fake] = set()
        self.hub.disconnect(fake)
        self.hub.disconnect(fake)
        self.assertEqual(self.disconnects, 1)


if __name__ == "__main__":
    unittest.main()
