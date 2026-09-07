"""
English: High-performance WebSocket management engine for Lila Framework.
         Provides connection tracking, room subscriptions, JSON event broadcasting,
         heartbeat ping/pong, and zero-overhead RAM/CPU usage.
Español: Motor de gestión WebSocket de alto rendimiento para Lila Framework.
         Provee seguimiento de conexiones, suscripción a salas (rooms), transmisión de eventos JSON,
         heartbeat ping/pong y consumo mínimo de RAM/CPU.
"""

from typing import Set, Dict, Callable, Optional, Any
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from lila.core.logger import Logger
from orjson import dumps as orjson_dumps, loads as orjson_loads
import asyncio
import uuid
import threading
from lila.core.cache import _REDIS_CLIENT


class WebSocketManager:
    """
    English: Core WebSocket Connection & Room Manager for Lila Framework.
    """
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.event_handlers: Dict[str, Callable] = {}
        self.id = str(uuid.uuid4())
        self.loop = None
        self._start_pubsub_listener()

    def _start_pubsub_listener(self) -> None:
        if _REDIS_CLIENT is None:
            return

        def listener():
            try:
                pubsub = _REDIS_CLIENT.pubsub()
                pubsub.subscribe("lila:ws:pubsub")
                for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            payload = orjson_loads(message["data"])
                            if payload.get("worker_id") != self.id:
                                if hasattr(self, "loop") and self.loop and self.loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        self._handle_pubsub_message(payload),
                                        self.loop
                                    )
                        except Exception:
                            pass
            except Exception:
                pass

        thread = threading.Thread(target=listener, daemon=True)
        thread.start()

    async def _handle_pubsub_message(self, payload: dict) -> None:
        event = payload.get("event")
        data = payload.get("data")
        room = payload.get("room")

        if room:
            await self._local_broadcast_to_room(room, event, data)
        else:
            await self._local_broadcast(event, data)

    async def connect(self, websocket: WebSocket, room: Optional[str] = None) -> None:
        """
        Accepts the WebSocket connection and registers it in the manager.
        """
        await websocket.accept()
        self.active_connections.add(websocket)

        if not hasattr(self, "loop") or self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        if room:
            self.join_room(websocket, room)

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Removes the WebSocket from all active connections and rooms.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        empty_rooms = []
        for room_name, clients in self.rooms.items():
            if websocket in clients:
                clients.remove(websocket)
                if not clients:
                    empty_rooms.append(room_name)
        
        for empty in empty_rooms:
            del self.rooms[empty]

    def join_room(self, websocket: WebSocket, room: str) -> None:
        """
        Adds a WebSocket client to a specific channel/room.
        """
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)

    def leave_room(self, websocket: WebSocket, room: str) -> None:
        """
        Removes a WebSocket client from a specific channel/room.
        """
        if room in self.rooms and websocket in self.rooms[room]:
            self.rooms[room].remove(websocket)
            if not self.rooms[room]:
                del self.rooms[room]

    async def emit_to(self, websocket: WebSocket, event: str, data: Any = None) -> bool:
        """
        Sends a JSON-encoded event message to a specific client.
        """
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                payload = orjson_dumps({"event": event, "data": data})
                await websocket.send_bytes(payload)
                return True
            except Exception as e:
                Logger.warning(f"WebSocket emit_to error: {e}")
                self.disconnect(websocket)
        return False

    async def _local_broadcast(self, event: str, data: Any = None, exclude: Optional[WebSocket] = None) -> int:
        if not self.active_connections:
            return 0

        payload = orjson_dumps({"event": event, "data": data})
        sent_count = 0
        dead_sockets = []

        for ws in self.active_connections:
            if ws == exclude:
                continue
            if ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_bytes(payload)
                    sent_count += 1
                except Exception:
                    dead_sockets.append(ws)

        for ws in dead_sockets:
            self.disconnect(ws)

        return sent_count

    async def broadcast(self, event: str, data: Any = None, exclude: Optional[WebSocket] = None) -> int:
        """
        Broadcasts a JSON event to all connected clients.
        Returns the number of successful deliveries.
        """
        sent_count = await self._local_broadcast(event, data, exclude)

        if _REDIS_CLIENT is not None:
            try:
                payload = {
                    "worker_id": self.id,
                    "event": event,
                    "data": data,
                    "room": None
                }
                _REDIS_CLIENT.publish("lila:ws:pubsub", orjson_dumps(payload))
            except Exception:
                pass

        return sent_count

    async def _local_broadcast_to_room(self, room: str, event: str, data: Any = None, exclude: Optional[WebSocket] = None) -> int:
        clients = self.rooms.get(room)
        if not clients:
            return 0

        payload = orjson_dumps({"event": event, "data": data})
        sent_count = 0
        dead_sockets = []

        for ws in clients:
            if ws == exclude:
                continue
            if ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_bytes(payload)
                    sent_count += 1
                except Exception:
                    dead_sockets.append(ws)

        for ws in dead_sockets:
            self.disconnect(ws)

        return sent_count

    async def broadcast_to_room(self, room: str, event: str, data: Any = None, exclude: Optional[WebSocket] = None) -> int:
        """
        Broadcasts a JSON event to all clients subscribed to a specific room.
        """
        sent_count = await self._local_broadcast_to_room(room, event, data, exclude)

        if _REDIS_CLIENT is not None:
            try:
                payload = {
                    "worker_id": self.id,
                    "event": event,
                    "data": data,
                    "room": room
                }
                _REDIS_CLIENT.publish("lila:ws:pubsub", orjson_dumps(payload))
            except Exception:
                pass

        return sent_count

    async def receive_event(self, websocket: WebSocket) -> tuple[Optional[str], Any]:
        """
        Receives and decodes a JSON event message from a client.
        Returns (event_name, payload_data).
        """
        try:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                decoded = orjson_loads(message["bytes"])
            elif "text" in message and message["text"]:
                decoded = orjson_loads(message["text"])
            else:
                return None, None

            if isinstance(decoded, dict):
                return decoded.get("event"), decoded.get("data")
            return "raw", decoded
        except Exception:
            return None, None

    def on(self, event_name: str):
        """
        Decorator to register an event handler.
        """
        def decorator(func: Callable):
            self.event_handlers[event_name] = func
            return func
        return decorator

    async def handle_connection(self, websocket: WebSocket, room: Optional[str] = None) -> None:
        """
        Convenience lifecycle loop that handles connection, event dispatching,
        heartbeat ping/pong, and automatic disconnection cleanup.
        """
        await self.connect(websocket, room=room)
        try:
            while True:
                event, data = await self.receive_event(websocket)
                if event is None:
                    break
                
                if event == "ping":
                    await self.emit_to(websocket, "pong", {"timestamp": data})
                    continue
                elif event == "join":
                    if isinstance(data, dict) and "room" in data:
                        self.join_room(websocket, data["room"])
                    elif isinstance(data, str):
                        self.join_room(websocket, data)
                    continue
                elif event == "leave":
                    if isinstance(data, dict) and "room" in data:
                        self.leave_room(websocket, data["room"])
                    elif isinstance(data, str):
                        self.leave_room(websocket, data)
                    continue

                handler = self.event_handlers.get(event)
                if handler:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(websocket, data)
                    else:
                        handler(websocket, data)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            Logger.warning(f"WebSocket connection error: {e}")
        finally:
            self.disconnect(websocket)
