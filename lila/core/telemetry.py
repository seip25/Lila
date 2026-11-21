"""Optional OpenTelemetry tracing: HTTP requests, SQL queries and tasks.

``pip install "lila-framework[otel]"`` and enable it::

    App(telemetry=True)          # or OTEL_ENABLED=true in .env

Standard OpenTelemetry variables configure the export (``OTEL_SERVICE_NAME``,
``OTEL_EXPORTER_OTLP_ENDPOINT``, ``OTEL_EXPORTER_OTLP_HEADERS``,
``OTEL_TRACES_SAMPLER``...); ``OTEL_TRACES_EXPORTER=console`` prints spans.
If your app already configured a TracerProvider, Lila uses it.

Spans are low-cardinality and private by default: ``GET /items/{id}`` (route
template, never the concrete path in the name), status code, SQL statement
text without parameters (truncated), task name/id. Incoming ``traceparent``
headers continue the caller's trace. Without the packages, nothing happens.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from lila.core.config import ENV_CONFIG
from lila.core.logger import Logger

_STATE: Dict[str, Any] = {"enabled": False, "tracer": None, "warned": False}
_ENGINES: List[Any] = []
_TRUE = {"1", "true", "yes", "on"}
MAX_STATEMENT = 1000


def available() -> bool:
    try:
        import opentelemetry.trace  # noqa: F401
        return True
    except ImportError:
        return False


def enabled() -> bool:
    return bool(_STATE["enabled"])


def tracer():
    return _STATE["tracer"]


def _setup_provider() -> None:
    from opentelemetry import trace

    current = trace.get_tracer_provider()
    if type(current).__name__ not in ("ProxyTracerProvider", "NoOpTracerProvider"):
        return  # the application configured its own provider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    service = os.environ.get("OTEL_SERVICE_NAME") or str(ENV_CONFIG.get("TITLE_PROJECT", "lila-app") or "lila-app")
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    exporter_name = (os.environ.get("OTEL_TRACES_EXPORTER") or "otlp").lower()
    if exporter_name == "console":
        exporter = ConsoleSpanExporter()
    elif exporter_name == "none":
        exporter = None
    else:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError:
            Logger.warning("[Lila] OTLP exporter missing: pip install opentelemetry-exporter-otlp-proto-http")
            exporter = None
        else:
            exporter = OTLPSpanExporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def enable(force: bool = False) -> bool:
    """Turns tracing on (idempotent). Returns False when OpenTelemetry is missing."""
    if _STATE["enabled"]:
        return True
    if not available():
        if not _STATE["warned"]:
            _STATE["warned"] = True
            Logger.warning('[Lila] telemetry requested but OpenTelemetry is not installed: pip install "lila-framework[otel]"')
        return False
    from opentelemetry import trace

    if not force:
        _setup_provider()
    _STATE["tracer"] = trace.get_tracer("lila")
    _STATE["enabled"] = True
    for engine in list(_ENGINES):
        _instrument(engine)
    return True


def requested(option: Any = None) -> bool:
    if option is not None:
        return bool(option)
    return str(ENV_CONFIG.get("OTEL_ENABLED", "") or os.environ.get("OTEL_ENABLED", "")).strip().lower() in _TRUE


# ── SQL ──────────────────────────────────────────────────────────────────────

def register_engine(engine: Any) -> None:
    """Called by Database.connect(); spans start once telemetry is enabled."""
    target = getattr(engine, "sync_engine", engine)
    if target in _ENGINES:
        return
    _ENGINES.append(target)
    if _STATE["enabled"]:
        _instrument(target)


def _instrument(engine: Any) -> None:
    if getattr(engine, "_lila_otel", False):
        return
    from sqlalchemy import event

    engine._lila_otel = True
    system = engine.dialect.name

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        tr = _STATE["tracer"]
        if tr is None:
            return
        operation = (statement or "").lstrip().split(" ", 1)[0].upper()[:16]
        span = tr.start_span(f"{operation or 'SQL'} {system}", kind=_kind("CLIENT"))
        span.set_attribute("db.system", system)
        span.set_attribute("db.statement", (statement or "")[:MAX_STATEMENT])
        span.set_attribute("db.operation", operation)
        conn.info.setdefault("_lila_spans", []).append(span)

    def _finish(conn, error: Optional[BaseException] = None) -> None:
        spans = conn.info.get("_lila_spans")
        if not spans:
            return
        span = spans.pop()
        if error is not None:
            span.record_exception(error)
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.ERROR, type(error).__name__))
        span.end()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        _finish(conn)

    @event.listens_for(engine, "handle_error")
    def _error(context):  # noqa: ANN001
        if context.connection is not None:
            _finish(context.connection, context.original_exception)


def _kind(name: str):
    from opentelemetry.trace import SpanKind

    return getattr(SpanKind, name)


# ── Tasks ────────────────────────────────────────────────────────────────────

class _NoSpan:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def task_span(name: str, task_id: Any = None):
    """``with task_span("send_email", 42):`` (no-op when disabled)."""
    tr = _STATE["tracer"]
    if tr is None:
        return _NoSpan()
    attributes = {"lila.task.name": str(name)}
    if task_id is not None:
        attributes["lila.task.id"] = str(task_id)
    return tr.start_as_current_span(f"task {name}", kind=_kind("CONSUMER"), attributes=attributes)


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _route_template(scope: dict) -> Optional[str]:
    endpoint = scope.get("endpoint")
    app = scope.get("app")
    if endpoint is None or app is None:
        return None
    cache = getattr(app, "_lila_route_templates", None)
    if cache is None:
        cache = {}
        try:
            for route in getattr(app, "routes", []):
                ep = getattr(route, "endpoint", None) or getattr(route, "app", None)
                if ep is not None and getattr(route, "path", None):
                    cache.setdefault(id(ep), route.path)
            app._lila_route_templates = cache
        except Exception:
            return None
    return cache.get(id(endpoint))


class PureASGITelemetryMiddleware:
    """Server span per HTTP request (and WebSocket connection)."""

    __slots__ = ("app",)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        tr = _STATE["tracer"]
        if tr is None or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        from opentelemetry import context as otel_context
        from opentelemetry.propagate import extract
        from opentelemetry.trace import Status, StatusCode

        carrier = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        parent = extract(carrier)
        method = scope.get("method", "WS") if scope["type"] == "http" else "WS"
        span = tr.start_span(method, context=parent, kind=_kind("SERVER"))
        span.set_attribute("http.request.method", method)
        span.set_attribute("url.path", scope.get("path", ""))
        span.set_attribute("url.scheme", scope.get("scheme", "http"))
        from opentelemetry.trace import set_span_in_context

        token = otel_context.attach(set_span_in_context(span, parent))
        status = 500
        start = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise
        finally:
            template = _route_template(scope)
            if template:
                span.set_attribute("http.route", template)
            span.update_name(f"{method} {template}" if template else (f"{method} {status}" if status == 404 else method))
            if scope["type"] == "http":
                span.set_attribute("http.response.status_code", status)
                if status >= 500:
                    span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("lila.duration_ms", round((time.perf_counter() - start) * 1000, 2))
            span.end()
            otel_context.detach(token)
