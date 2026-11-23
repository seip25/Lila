"""Server-Sent Events: simple real-time updates over plain HTTP.

One-way server → browser streams (notifications, progress, dashboards) with
automatic reconnection in the browser, no WebSocket server needed.

    from lila.core.sse import Channel, EventStream

    notifications = Channel("notifications")

    @router.get("/events")
    async def events(request: Request):
        user = await Session.get_async(request, "auth")
        return notifications.stream(request, key=f"user:{user['id']}")   # + broadcasts

    await notifications.publish({"message": "Saved"}, event="notice")                  # everyone
    await notifications.publish({"message": "Hi"}, event="notice", to="user:7")        # one user

    @router.get("/progress")
    async def progress(request: Request):
        async def steps():
            for pct in range(0, 101, 10):
                yield {"event": "progress", "data": {"pct": pct}}
                await asyncio.sleep(0.2)
        return EventStream(request, steps())

In the browser: ``lilaSSE("/events").on("notice", data => ...)`` or
``<div data-sse="/events" data-sse-event="notice" data-sse-toast>``.
With ``CACHE_DRIVER=redis`` channel messages reach the subscribers of every
worker (Redis pub/sub); otherwise they stay in the current process.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any, AsyncIterator, Dict, Optional, Set

from starlette.responses import StreamingResponse

from lila.core.responses import orjson_dumps, orjson_loads

HEARTBEAT_SECONDS = 15.0
_PROCESS_ID = uuid.uuid4().hex  # skips our own Redis echoes
_SHUTDOWN = threading.Event()
_ACTIVE_SIGNALS: Set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()
_SIGNALS_LOCK = threading.Lock()


def signal_shutdown() -> None:
    """Wake all active SSE streams so servers exit without waiting for idle tabs."""
    _SHUTDOWN.set()
    with _SIGNALS_LOCK:
        targets = list(_ACTIVE_SIGNALS)
    for loop, ev in targets:
        try:
            if not loop.is_closed():
                loop.call_soon_threadsafe(ev.set)
        except Exception:
            pass


def reset_shutdown() -> None:
    """Clear the global SSE shutdown flag (used on app startup / tests)."""
    _SHUTDOWN.clear()


def is_shutting_down() -> bool:
    return _SHUTDOWN.is_set()


def format_event(data: Any = None, event: Optional[str] = None, id: Optional[str] = None,
                 retry: Optional[int] = None) -> bytes:
    lines = []
    if event:
        lines.append(f"event: {str(event).replace(chr(10), ' ')}")
    if id is not None:
        lines.append(f"id: {str(id).replace(chr(10), ' ')}")
    if retry is not None:
        lines.append(f"retry: {int(retry)}")
    payload = data if isinstance(data, str) else orjson_dumps(data).decode("utf-8")
    for line in payload.splitlines() or [""]:
        lines.append(f"data: {line}")
    return ("\n".join(lines) + "\n\n").encode("utf-8")


class EventStream(StreamingResponse):
    """Streams events from an async iterator; sends heartbeats and stops when
    the client disconnects. Items may be dicts ``{"event", "data", "id", "retry"}``
    or plain values (sent as ``data``)."""

    def __init__(self, request, source: AsyncIterator[Any], heartbeat: float = HEARTBEAT_SECONDS,
                 retry: int = 3000, headers: Optional[dict] = None):
        self._request = request
        self._source = source
        self._heartbeat = heartbeat
        self._retry = retry
        base_headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Nginx: do not buffer the stream
            "Connection": "keep-alive",
        }
        base_headers.update(headers or {})
        super().__init__(self._generate(), media_type="text/event-stream", headers=base_headers)

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except asyncio.CancelledError:
            return

    async def _generate(self):
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()
        if _SHUTDOWN.is_set():
            stop_event.set()
        sig = (loop, stop_event)
        with _SIGNALS_LOCK:
            _ACTIVE_SIGNALS.add(sig)

        yield format_event(event="ready", data={"ok": True}, retry=self._retry)
        iterator = self._source.__aiter__()
        pending: Optional[asyncio.Task] = None
        stop_task: Optional[asyncio.Task] = None
        try:
            while not stop_event.is_set() and not _SHUTDOWN.is_set():
                if pending is None:
                    pending = asyncio.ensure_future(iterator.__anext__())
                if stop_task is None:
                    stop_task = asyncio.ensure_future(stop_event.wait())
                done, _ = await asyncio.wait(
                    {pending, stop_task},
                    timeout=self._heartbeat,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_event.is_set() or _SHUTDOWN.is_set() or await self._request.is_disconnected():
                    break
                if not done:
                    yield b": ping\n\n"
                    continue
                if stop_task in done:
                    break
                try:
                    item = pending.result()
                except StopAsyncIteration:
                    break
                finally:
                    pending = None
                if isinstance(item, dict) and ("data" in item or "event" in item):
                    yield format_event(item.get("data"), item.get("event"), item.get("id"), item.get("retry"))
                else:
                    yield format_event(item)
        except (asyncio.CancelledError, GeneratorExit):
            return
        finally:
            with _SIGNALS_LOCK:
                _ACTIVE_SIGNALS.discard(sig)
            for task in (pending, stop_task):
                if task is not None and not task.done():
                    task.cancel()
            aclose = getattr(iterator, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except (Exception, asyncio.CancelledError):
                    pass


class Channel:
    """Named pub/sub channel for SSE subscribers (optionally addressed by key)."""

    _channels: Dict[str, "Channel"] = {}

    def __new__(cls, name: str, max_queue: int = 100):
        existing = cls._channels.get(name)
        if existing is not None:
            return existing
        obj = super().__new__(cls)
        cls._channels[name] = obj
        return obj

    def __init__(self, name: str, max_queue: int = 100):
        if getattr(self, "_ready", False):
            return
        self.name = name
        self.max_queue = max_queue
        self._subscribers: Set[tuple] = set()  # (queue, key)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._redis_started = False
        self._ready = True

    @property
    def subscribers(self) -> int:
        return len(self._subscribers)

    def _deliver(self, message: dict) -> int:
        delivered = 0
        to = message.get("to")
        for queue, key in list(self._subscribers):
            if to is not None and key != to:
                continue
            if queue.full():
                try:
                    queue.get_nowait()  # slow client: drop its oldest message
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)
            delivered += 1
        return delivered

    async def publish(self, data: Any = None, event: Optional[str] = None, to: Optional[str] = None) -> int:
        """Sends to every subscriber (or only to ``key == to``). Returns local deliveries."""
        message = {"event": event, "data": data, "to": to}
        delivered = self._deliver(message)
        await self._publish_redis(message)
        return delivered

    def stream(self, request, key: Optional[str] = None, heartbeat: float = HEARTBEAT_SECONDS) -> EventStream:
        self._loop = asyncio.get_running_loop()
        self._ensure_redis()
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue)
        entry = (queue, key)

        async def source():
            self._subscribers.add(entry)
            try:
                while True:
                    message = await queue.get()
                    yield {"event": message.get("event"), "data": message.get("data")}
            finally:
                self._subscribers.discard(entry)

        return EventStream(request, source(), heartbeat=heartbeat)

    # Redis fan-out (only when CACHE_DRIVER=redis and Redis answers)
    async def _publish_redis(self, message: dict) -> None:
        from lila.core.cache import Cache

        if Cache._get_driver() != "redis":
            return
        client = await Cache._get_redis_async()
        if client is None:
            return
        try:
            await client.publish(f"lila:sse:{self.name}", orjson_dumps({**message, "origin": _PROCESS_ID}))
        except Exception:
            pass

    def _ensure_redis(self) -> None:
        from lila.core.cache import Cache, has_redis

        if self._redis_started or not has_redis() or Cache._get_driver() != "redis":
            return
        self._redis_started = True
        me = _PROCESS_ID

        def listen():
            import time

            while True:
                client = Cache._get_redis_sync()
                if client is None:
                    time.sleep(5)
                    continue
                try:
                    pubsub = client.pubsub()
                    pubsub.subscribe(f"lila:sse:{self.name}")
                    for raw in pubsub.listen():
                        if raw.get("type") != "message":
                            continue
                        message = orjson_loads(raw["data"])
                        if message.get("origin") == me or self._loop is None:
                            continue
                        self._loop.call_soon_threadsafe(self._deliver, message)
                except Exception:
                    time.sleep(2)

        threading.Thread(target=listen, daemon=True, name=f"lila-sse-{self.name}").start()
