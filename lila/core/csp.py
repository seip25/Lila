"""Content-Security-Policy with per-response nonces.

``App(csp=True)`` sends a strict policy on every HTML response::

    script-src 'nonce-<random>' 'strict-dynamic' 'self' https: 'unsafe-inline'

Modern browsers only run scripts carrying the nonce (and the scripts those
load: lila-client.js SPA navigations, Vite chunks, lazy imports); the
``'self' https: 'unsafe-inline'`` part is the CSP2 fallback older browsers use
and newer ones ignore when a nonce is present. Inline event handlers
(``onclick="..."``) are blocked: use ``addEventListener`` or ``data-*``.

Templates write a placeholder (``{{ nonce_attr }}`` / ``{{ csp_nonce }}``) and
this middleware swaps it for a fresh nonce per response, so route caches
(``cache=60``) and ETags keep working with stable bodies.

Options::

    App(csp=True)                       # enforce the default policy
    App(csp="report-only")              # Content-Security-Policy-Report-Only
    App(csp={"img-src": ["https://cdn.example"],      # extra sources
             "connect-src": ["wss://realtime.example"],
             "report-uri": "/csp-report", "report_only": False})
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, Iterable, List, Optional, Union

from markupsafe import Markup
from starlette.types import ASGIApp, Receive, Scope, Send

# Same length as a real nonce: Content-Length never changes when swapping.
PLACEHOLDER = "LilaCspNonce000000000000"
PLACEHOLDER_BYTES = PLACEHOLDER.encode("ascii")

DEFAULT_POLICY: Dict[str, List[str]] = {
    "default-src": ["'self'"],
    "script-src": ["'strict-dynamic'", "'self'", "https:", "'unsafe-inline'"],
    # Tailwind's browser runtime and Vite inject <style> tags in development.
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", "https:"],
    "font-src": ["'self'", "data:", "https:"],
    "connect-src": ["'self'"],
    "media-src": ["'self'", "blob:", "data:"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
}


def new_nonce() -> str:
    nonce = secrets.token_urlsafe(18)  # 24 chars, like PLACEHOLDER
    return nonce


def is_enabled(request: Any) -> bool:
    try:
        return bool(getattr(request.state, "csp", False))
    except Exception:
        return False


def nonce_value(request: Any) -> str:
    """The nonce placeholder for templates (``""`` when CSP is off)."""
    return PLACEHOLDER if is_enabled(request) else ""


def nonce_attr(request: Any) -> Markup:
    """`` nonce="..."`` for ``<script{{ nonce_attr }}>`` (empty when CSP is off)."""
    return Markup(f' nonce="{PLACEHOLDER}"') if is_enabled(request) else Markup("")


def _as_list(value: Union[str, Iterable[str], None]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v for v in value.split() if v]
    return [str(v) for v in value]


class CSPConfig:
    def __init__(self, option: Any):
        self.report_only = option == "report-only"
        self.policy = {key: list(values) for key, values in DEFAULT_POLICY.items()}
        self.report_uri: Optional[str] = None
        if isinstance(option, dict):
            for key, value in option.items():
                if key in ("report_only", "report-only"):
                    self.report_only = bool(value)
                elif key in ("report_uri", "report-uri"):
                    self.report_uri = str(value)
                elif key.endswith("!"):
                    # "script-src!": [...] replaces the directive instead of extending it.
                    self.policy[key[:-1]] = _as_list(value)
                else:
                    current = self.policy.setdefault(key, [])
                    for item in _as_list(value):
                        if item not in current:
                            current.append(item)

    def header_name(self) -> bytes:
        return b"content-security-policy-report-only" if self.report_only else b"content-security-policy"

    def build(self, nonce: str, extra: Optional[Dict[str, List[str]]] = None) -> str:
        policy = {key: list(values) for key, values in self.policy.items()}
        for key, values in (extra or {}).items():
            policy.setdefault(key, [])
            policy[key] += [v for v in values if v not in policy[key]]
        policy["script-src"] = [f"'nonce-{nonce}'"] + policy.get("script-src", [])
        parts = [f"{key} {' '.join(values)}".strip() for key, values in policy.items() if values is not None]
        if self.report_uri:
            parts.append(f"report-uri {self.report_uri}")
        return "; ".join(parts)


def _dev_sources() -> Dict[str, List[str]]:
    """Vite dev server (HMR) origins, only while it is in use."""
    try:
        from lila.core.vite import ViteBridge

        url = ViteBridge.dev_url()
    except Exception:
        url = None
    if not url:
        return {}
    ws = url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    return {"script-src": [url], "style-src": [url], "connect-src": [url, ws], "img-src": [url], "font-src": [url]}


class PureASGICSPMiddleware:
    """Adds the CSP header to HTML responses and fills the nonce placeholder.

    HTML responses lose their ``ETag`` (and HTML requests their
    ``If-None-Match``): a cached page would keep an old nonce that no longer
    matches the header. JSON/static responses are untouched.
    """

    __slots__ = ("app", "config")

    def __init__(self, app: ASGIApp, csp: Any = True):
        self.app = app
        self.config = csp if isinstance(csp, CSPConfig) else CSPConfig(csp)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["csp"] = True
        nonce = new_nonce()
        state["csp_nonce"] = nonce

        accept = b""
        for name, value in scope.get("headers", []):
            if name == b"accept":
                accept = value
                break
        if b"text/html" in accept:
            scope = dict(scope)
            scope["headers"] = [(n, v) for n, v in scope.get("headers", []) if n != b"if-none-match"]

        start: Optional[dict] = None
        chunks: List[bytes] = []
        html = False

        async def send_wrapper(message):
            nonlocal start, html
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                content_type = b""
                for name, value in headers:
                    if name.lower() == b"content-type":
                        content_type = value.lower()
                        break
                html = content_type.startswith(b"text/html")
                if not html:
                    await send(message)
                    return
                start = message
                return
            if message["type"] == "http.response.body" and html:
                chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                body = b"".join(chunks).replace(PLACEHOLDER_BYTES, nonce.encode("ascii"))
                is_head = scope.get("method") == "HEAD"
                headers = [
                    (n, v) for n, v in start.get("headers", [])
                    if n.lower() not in (b"etag", self.config.header_name())
                    and not (n.lower() == b"content-length" and not is_head)
                ]
                if not is_head:
                    headers.append((b"content-length", str(len(body)).encode()))
                headers.append((self.config.header_name(), self.config.build(nonce, _dev_sources()).encode()))
                await send({**start, "headers": headers})
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return
            await send(message)

        await self.app(scope, receive, send_wrapper)
