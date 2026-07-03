"""
English: High-performance WebSocket management engine for Lila Framework.
         Provides connection tracking, room subscriptions, JSON event broadcasting,
         heartbeat ping/pong, and zero-overhead RAM/CPU usage.
Español: Motor de gestión WebSocket de alto rendimiento para Lila Framework.
         Provee seguimiento de conexiones, suscripción a salas (rooms), transmisión de eventos JSON,
         heartbeat ping/pong y consumo mínimo de RAM/CPU.
"""

import asyncio
from typing import Any, Dict, Set, Optional, Callable
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from lila.core.responses import orjson_dumps, orjson_loads
from lila.core.logger import Logger


class WebSocketManager:
    """
    English: Core WebSocket Connection & Room Manager for Lila Framework.
    Español: Gestor central de conexiones y salas WebSocket para Lila Framework.
    """

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.event_handlers: Dict[str, Callable] = {}

    async def connect(self, websocket: WebSocket, room: Optional[str] = None) -> None:
        """
        Accepts the WebSocket connection and registers it in the manager.
        """
        await websocket.accept()
        self.active_connections.add(websocket)
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

    async def broadcast(self, event: str, data: Any = None, exclude: Optional[WebSocket] = None) -> int:
        """
        Broadcasts a JSON event to all connected clients.
        Returns the number of successful deliveries.
        """
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

    async def broadcast_to_room(self, room: str, event: str, data: Any = None, exclude: Optional[WebSocket] = None) -> int:
        """
        Broadcasts a JSON event to all clients subscribed to a specific room.
        """
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
        Usage:
            @ws_manager.on("chat_message")
            async def handle_chat(websocket, data):
                await ws_manager.broadcast("chat_message", data)
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
