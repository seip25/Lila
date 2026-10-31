"""Lila Framework v2.0.0 Simplified WebSocket Engine.
Event-driven WebSocketHub with declarative decorators, rooms, broadcast,
and zero-overhead Redis Pub/Sub scaling.
"""

import asyncio
import time
import uuid
import threading
from typing import Set, Dict, Callable, Optional, Any
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from lila.core.logger import Logger
from lila.core.responses import orjson_dumps, orjson_loads
from lila.core.cache import Cache, has_redis


class WebSocketHub:
    """Core WebSocket Hub supporting declarative events and rooms."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.client_rooms: Dict[WebSocket, Set[str]] = {}
        self.event_handlers: Dict[str, Callable] = {}
        self.connect_handlers: list = []
        self.disconnect_handlers: list = []
        self.worker_id = uuid.uuid4().hex
        self.loop = None
        self._pubsub_started = False
        self._send_locks: Dict[WebSocket, asyncio.Lock] = {}

    def _ensure_pubsub(self) -> None:
        """Starts the Redis listener lazily (Redis may be configured after import)."""
        if self._pubsub_started or not has_redis():
            return
        from lila.core.config import ConfigLoader

        ConfigLoader.load()
        if Cache._get_driver() != "redis":
            return

        def _listener():
            while True:
                r = Cache._get_redis_sync()
                if not r:
                    time.sleep(5)
                    continue
                try:
                    ps = r.pubsub()
                    ps.subscribe("lila:ws:pubsub")
                    for msg in ps.listen():
                        if msg.get("type") == "message":
                            try:
                                payload = orjson_loads(msg["data"])
                                if (
                                    payload.get("worker_id") != self.worker_id
                                    and self.loop
                                    and self.loop.is_running()
                                ):
                                    asyncio.run_coroutine_threadsafe(
                                        self._handle_pubsub_msg(payload), self.loop
                                    )
                            except Exception:
                                pass
                except Exception:
                    time.sleep(2)

        self._pubsub_started = True
        threading.Thread(target=_listener, daemon=True).start()

    async def _handle_pubsub_msg(self, payload: dict) -> None:
        event = payload.get("event")
        data = payload.get("data")
        room = payload.get("room")
        await self._local_broadcast(event, data, room=room)

    def on(self, event_name: str):
        """Decorator to register event handler: @ws.on('chat:message')"""
        def decorator(fn: Callable):
            self.event_handlers[event_name] = fn
            return fn
        return decorator

    def on_connect(self, fn: Callable):
        """Decorator for connect lifecycle hook."""
        self.connect_handlers.append(fn)
        return fn

    def on_disconnect(self, fn: Callable):
        """Decorator for disconnect lifecycle hook."""
        self.disconnect_handlers.append(fn)
        return fn

    async def connect(self, websocket: WebSocket, room: Optional[str] = None) -> None:
        """Accepts connection and tracks in active set."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_rooms[websocket] = set()
        self._send_locks[websocket] = asyncio.Lock()

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        self._ensure_pubsub()

        if room:
            self.join_room(websocket, room)

        for handler in self.connect_handlers:
            try:
                res = handler(websocket)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                Logger.error(f"WebSocket on_connect handler error: {e}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes websocket from active connections and rooms."""
        self.active_connections.discard(websocket)
        self._send_locks.pop(websocket, None)
        rooms_to_leave = set(self.client_rooms.pop(websocket, set()))
        for r_name in rooms_to_leave:
            self.leave_room(websocket, r_name)

        for handler in self.disconnect_handlers:
            try:
                res = handler(websocket)
                if asyncio.iscoroutine(res):
                    # Schedule task if event loop is alive
                    if self.loop and self.loop.is_running():
                        self.loop.create_task(res)
            except Exception as e:
                Logger.error(f"WebSocket on_disconnect handler error: {e}")

    def join_room(self, websocket: WebSocket, room: str) -> None:
        """Adds connection to specified room."""
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)
        if websocket in self.client_rooms:
            self.client_rooms[websocket].add(room)

    def leave_room(self, websocket: WebSocket, room: str) -> None:
        """Removes connection from room."""
        if room in self.rooms:
            self.rooms[room].discard(websocket)
            if not self.rooms[room]:
                del self.rooms[room]
        if websocket in self.client_rooms:
            self.client_rooms[websocket].discard(room)

    async def _send(self, websocket: WebSocket, payload: str, timeout: float = 2.0) -> bool:
        lock = self._send_locks.get(websocket)
        if lock is None:
            lock = asyncio.Lock()
            self._send_locks[websocket] = lock
        try:
            async with lock:
                if websocket.client_state != WebSocketState.CONNECTED:
                    return False
                await asyncio.wait_for(websocket.send_text(payload), timeout=timeout)
                return True
        except Exception:
            return False

    async def emit(self, websocket: WebSocket, event: str, data: Any = None) -> bool:
        """Sends an event packet to a specific websocket client."""
        payload = orjson_dumps({"event": event, "data": data}).decode("utf-8")
        sent = await self._send(websocket, payload)
        if not sent:
            self.disconnect(websocket)
        return sent

    async def _local_broadcast(
        self, event: str, data: Any = None, room: Optional[str] = None, exclude: Optional[WebSocket] = None
    ) -> int:
        targets = list(self.rooms.get(room, set()) if room else self.active_connections)
        if not targets:
            return 0

        payload = orjson_dumps({"event": event, "data": data, "room": room}).decode("utf-8")
        clients = [
            client for client in targets
            if client is not exclude and client.client_state == WebSocketState.CONNECTED
        ]
        if not clients:
            return 0

        results = await asyncio.gather(
            *(self._send(client, payload) for client in clients), return_exceptions=True
        )
        sent_count = 0
        for client, result in zip(clients, results):
            if result is True:
                sent_count += 1
            else:
                self.disconnect(client)
        return sent_count

    async def broadcast(
        self, event: str, data: Any = None, room: Optional[str] = None, exclude: Optional[WebSocket] = None
    ) -> int:
        """Broadcasts event to a room or globally to all clients across workers."""
        self._ensure_pubsub()
        # 1. Broadcast locally
        count = await self._local_broadcast(event, data, room=room, exclude=exclude)

        # 2. Publish to Redis if available
        if Cache._get_driver() == "redis":
            r = await Cache._get_redis_async()
            if r is not None:
                try:
                    pubsub_payload = orjson_dumps({
                        "worker_id": self.worker_id,
                        "event": event,
                        "data": data,
                        "room": room,
                    })
                    await r.publish("lila:ws:pubsub", pubsub_payload)
                except Exception:
                    pass

        return count

    # Alias for backward compatibility
    emit_to = emit
    broadcast_to_room = broadcast

    async def handle_connection(self, websocket: WebSocket, default_room: Optional[str] = None) -> None:
        """Automated connection loop handling ping/pong and event dispatch."""
        await self.connect(websocket, room=default_room)
        try:
            while True:
                msg = await websocket.receive_text()
                if len(msg) > 1_048_576:
                    await websocket.close(code=1009)
                    break
                # Heartbeat ping check
                if msg == "ping":
                    await websocket.send_text("pong")
                    continue

                try:
                    parsed = orjson_loads(msg)
                    if not isinstance(parsed, dict):
                        continue
                except Exception:
                    continue

                event = parsed.get("event")
                data = parsed.get("data")

                if event == "ping":
                    await websocket.send_text('{"event": "pong"}')
                    continue

                if event == "join":
                    room_name = str(data or "")
                    if room_name:
                        self.join_room(websocket, room_name)
                    continue

                if event == "leave":
                    room_name = str(data or "")
                    if room_name:
                        self.leave_room(websocket, room_name)
                    continue

                if event in self.event_handlers:
                    handler = self.event_handlers[event]
                    try:
                        res = handler(websocket, data)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as err:
                        Logger.error(f"WebSocket event '{event}' handler error: {err}")
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            self.disconnect(websocket)


# Global default hub instance
ws = WebSocketHub()
WebSocketManager = WebSocketHub

