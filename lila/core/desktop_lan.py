"""Opt-in LAN Gateway with OTP Pairing for Lila Desktop applications.

Keeps the main desktop server bound strictly to ``127.0.0.1`` and protected by
``LILA_DESKTOP_TOKEN``. When explicitly enabled (``DESKTOP_LAN=True``,
``lila desktop dev --lan``, or ``desktop.startLan()``), ``DesktopLanGateway``
listens on ``0.0.0.0:<port>`` and:

1. Pairs phones/browsers/LAN peers using a short-lived 6-digit OTP PIN
   (``/_lila/lan/pair``), issuing a signed ``HttpOnly`` ``lila_lan`` cookie
   tied to an in-memory session registry (revocable at any moment).
2. Enforces per-IP OTP brute-force lockout (5 failures -> 5 min 429).
3. Enforces optional ``DESKTOP_LAN_ALLOW`` / ``DESKTOP_LAN_DENY`` path rules.
4. Strips any client-spoofed ``X-Forwarded-*`` / ``X-Lila-Desktop-Token`` /
   ``X-Lila-Lan*`` headers and injects trusted ``X-Forwarded-For``,
   ``X-Lila-Lan: 1``, ``X-Lila-Lan-IP``, and ``X-Lila-Lan-Proxy`` before
   forwarding HTTP, SSE, and WebSocket traffic to ``127.0.0.1``.
"""

from __future__ import annotations

import asyncio
import fnmatch
import hmac
import html as _html
import json
import os
import secrets
import socket
import threading
import time
from http.cookies import SimpleCookie
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qs, urlsplit

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from lila.core.config import ENV_CONFIG, get_secret_key

LAN_COOKIE_NAME = "lila_lan"
PAIR_PATH = "/_lila/lan/pair"
LOGOUT_PATH = "/_lila/lan/logout"
MAX_HEADER_BYTES = 32_768
MAX_PAIR_BODY_BYTES = 4_096
MAX_OTP_FAILURES = 5
OTP_LOCK_SECONDS = 300
DEFAULT_OTP_TTL = 300
LAN_SESSION_MAX_AGE = 43_200  # 12 hours

_STATIC_ALWAYS_ALLOW = ("/public", "/js", "/css", "/img", "/build", "/fonts", "/favicon.ico")

_STATE_LOCK = threading.Lock()
_LOCAL_PORT = 0
_ACTIVE_GATEWAY: Optional["DesktopLanGateway"] = None


def detect_lan_ip() -> str:
    """Return this machine's local network IPv4 address (no packet sent)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        return ip or "127.0.0.1"
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _split_patterns(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = str(value).replace("\n", ",").split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def _match_pattern(pattern: str, path: str) -> bool:
    pat = pattern.strip()
    if not pat:
        return False
    if not pat.startswith("/"):
        pat = "/" + pat
    if any(ch in pat for ch in "*?["):
        return fnmatch.fnmatchcase(path, pat)
    base = pat.rstrip("/") or "/"
    return path == base or (base != "/" and path.startswith(base + "/"))


def _clean_ip(addr: Any) -> str:
    raw = str(addr or "").strip()
    if raw.startswith("::ffff:"):
        raw = raw[7:]
    return raw or "unknown"


def is_lan_request(request: Any) -> bool:
    state = getattr(request, "state", None)
    return bool(getattr(state, "is_lan", False))


def lan_client_ip(request: Any) -> Optional[str]:
    state = getattr(request, "state", None)
    val = getattr(state, "lan_ip", None)
    return str(val) if val else None


def _pair_html(error_msg: str = "", info_msg: str = "") -> bytes:
    err_block = (
        f'<div style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;padding:.75rem;border-radius:10px;font-size:.875rem;margin-bottom:1rem">{_html.escape(error_msg)}</div>'
        if error_msg
        else ""
    )
    info_block = (
        f'<div style="background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;padding:.75rem;border-radius:10px;font-size:.875rem;margin-bottom:1rem">{_html.escape(info_msg)}</div>'
        if info_msg
        else ""
    )
    app_title = _html.escape(str(ENV_CONFIG.get("TITLE_PROJECT", "Lila Desktop") or "Lila Desktop"))
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Pair Device — {app_title}</title>
<style>
  body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#0f172a;font-family:system-ui,-apple-system,sans-serif;padding:1rem}}
  .card{{width:100%;max-width:380px;background:#fff;border-radius:18px;padding:1.75rem;box-shadow:0 20px 50px rgba(0,0,0,.35)}}
  h1{{margin:0 0 .35rem;font-size:1.25rem;font-weight:800}}
  p{{margin:0 0 1.25rem;font-size:.875rem;color:#475569;line-height:1.45}}
  label{{display:block;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#475569;margin-bottom:.4rem}}
  input{{width:100%;box-sizing:border-box;font-size:1.5rem;letter-spacing:.35em;text-align:center;font-weight:800;padding:.75rem;border:1.5px solid #cbd5e1;border-radius:12px;margin-bottom:1rem}}
  input:focus{{outline:none;border-color:#4f46e5}}
  button{{width:100%;padding:.85rem 1rem;border:0;border-radius:12px;background:#4f46e5;color:#fff;font-weight:700;font-size:.95rem;cursor:pointer}}
  button:hover{{background:#4338ca}}
</style>
</head>
<body>
  <div class="card">
    <h1>Pair with {app_title}</h1>
    <p>Enter the 6-digit PIN shown on the host desktop screen to connect this device on the local network.</p>
    {err_block}{info_block}
    <form method="post" action="{PAIR_PATH}">
      <label for="code">6-Digit Pairing PIN</label>
      <input id="code" name="code" type="text" inputmode="numeric" pattern="[0-9]{{4,12}}" maxlength="12" autocomplete="one-time-code" autofocus required/>
      <button type="submit">Connect Device</button>
    </form>
  </div>
</body>
</html>"""
    return doc.encode("utf-8")


def _http_response(
    status_code: int,
    reason: str,
    body: bytes,
    content_type: str = "text/plain; charset=utf-8",
    extra_headers: Optional[List[tuple[str, str]]] = None,
) -> bytes:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Connection", "close"),
        ("Cache-Control", "no-store"),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    head = f"HTTP/1.1 {status_code} {reason}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers) + "\r\n"
    return head.encode("latin-1") + body


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65_536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            if not writer.is_closing():
                writer.close()
        except Exception:
            pass


class DesktopLanGateway:
    """Async TCP/HTTP/WS reverse-proxy binding ``0.0.0.0`` with OTP pairing."""

    def __init__(
        self,
        target_port: int,
        lan_port: int = 0,
        otp_ttl: int = DEFAULT_OTP_TTL,
        allow: Optional[Sequence[str]] = None,
        deny: Optional[Sequence[str]] = None,
        desktop_token: Optional[str] = None,
        proxy_secret: Optional[str] = None,
        bind_host: str = "0.0.0.0",
    ):
        self.target_port = int(target_port)
        self.lan_port = int(lan_port or 0)
        self.otp_ttl = max(30, int(otp_ttl or DEFAULT_OTP_TTL))
        self.allow = list(allow) if allow is not None else _split_patterns(ENV_CONFIG.get("DESKTOP_LAN_ALLOW", ""))
        self.deny = list(deny) if deny is not None else _split_patterns(ENV_CONFIG.get("DESKTOP_LAN_DENY", ""))
        self.desktop_token = os.environ.get("LILA_DESKTOP_TOKEN", "") if desktop_token is None else str(desktop_token)
        self.proxy_secret = proxy_secret or secrets.token_hex(24)
        self.bind_host = bind_host

        self._lock = threading.Lock()
        self._otp = ""
        self._otp_expires_at = 0.0
        self._sessions: Dict[str, dict] = {}
        self._failures: Dict[str, tuple[int, float]] = {}

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[asyncio.base_events.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._ready_event = threading.Event()
        self._start_error: Optional[Exception] = None
        self.bound_port = 0
        self.rotate_otp(self.otp_ttl)

    def _serializer(self) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(get_secret_key(), salt="lila-lan-session")

    def rotate_otp(self, ttl: Optional[int] = None) -> dict:
        ttl_sec = max(30, int(ttl if ttl is not None else self.otp_ttl))
        with self._lock:
            self._otp = f"{secrets.randbelow(1_000_000):06d}"
            self._otp_expires_at = time.time() + ttl_sec
        return self.status()

    def revoke_sessions(self) -> int:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
        return count

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._loop is not None and not self._loop.is_closed()

    def status(self) -> dict:
        ip = detect_lan_ip()
        port = self.bound_port or self.lan_port
        with self._lock:
            remaining = max(0, int(round(self._otp_expires_at - time.time())))
            sess_count = len(self._sessions)
            otp = self._otp
        base = f"http://{ip}:{port}" if port else ""
        return {
            "running": self.is_running,
            "host_ip": ip,
            "port": port,
            "url": base,
            "pair_url": f"{base}{PAIR_PATH}?code={otp}" if base else "",
            "otp": otp,
            "otp_expires_in": remaining,
            "active_sessions": sess_count,
            "allow": list(self.allow),
            "deny": list(self.deny),
        }

    def start(self) -> dict:
        if self.is_running:
            return self.status()
        os.environ["LILA_LAN_PROXY_SECRET"] = self.proxy_secret
        self._ready_event.clear()
        self._start_error = None

        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                srv = loop.run_until_complete(
                    asyncio.start_server(self._handle_client, self.bind_host, self.lan_port)
                )
                self._server = srv
                if srv.sockets:
                    self.bound_port = int(srv.sockets[0].getsockname()[1])
                self._ready_event.set()
                loop.run_forever()
            except Exception as exc:
                self._start_error = exc
                self._ready_event.set()
            finally:
                try:
                    if self._server is not None:
                        self._server.close()
                        loop.run_until_complete(self._server.wait_closed())
                except Exception:
                    pass
                self._server = None
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                loop.close()

        self._thread = threading.Thread(target=_runner, daemon=True, name="lila-desktop-lan")
        self._thread.start()
        self._ready_event.wait(timeout=5.0)
        if self._start_error is not None:
            self.stop()
            raise self._start_error
        return self.status()

    def stop(self) -> None:
        srv = self._server
        loop = self._loop
        if loop is not None and not loop.is_closed():
            def _shutdown():
                if srv is not None:
                    srv.close()
                loop.stop()

            try:
                loop.call_soon_threadsafe(_shutdown)
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._server = None
        self._loop = None
        self._thread = None
        self.bound_port = 0
        if os.environ.get("LILA_LAN_PROXY_SECRET") == self.proxy_secret:
            os.environ.pop("LILA_LAN_PROXY_SECRET", None)

    def _path_allowed(self, path: str) -> bool:
        for prefix in _STATIC_ALWAYS_ALLOW:
            if path == prefix or path.startswith(prefix + "/"):
                return True
        if self.deny and any(_match_pattern(p, path) for p in self.deny):
            return False
        if self.allow:
            return any(_match_pattern(p, path) for p in self.allow)
        return True

    def _verify_cookie(self, headers: List[tuple[str, str]]) -> Optional[str]:
        raw_cookie = ""
        for k, v in headers:
            if k.lower() == "cookie":
                raw_cookie = f"{raw_cookie}; {v}" if raw_cookie else v
        if not raw_cookie:
            return None
        parsed = SimpleCookie()
        try:
            parsed.load(raw_cookie)
        except Exception:
            return None
        morsel = parsed.get(LAN_COOKIE_NAME)
        if morsel is None or not morsel.value:
            return None
        try:
            sid = self._serializer().loads(morsel.value, max_age=LAN_SESSION_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return None
        with self._lock:
            if sid in self._sessions:
                return str(sid)
        return None

    def _check_rate_lock(self, remote_ip: str) -> Optional[int]:
        now = time.time()
        with self._lock:
            count, locked_until = self._failures.get(remote_ip, (0, 0.0))
            if locked_until > now:
                return max(1, int(locked_until - now))
            if locked_until and locked_until <= now:
                self._failures.pop(remote_ip, None)
        return None

    def _record_failure(self, remote_ip: str) -> Optional[int]:
        now = time.time()
        with self._lock:
            count, _ = self._failures.get(remote_ip, (0, 0.0))
            count += 1
            if count >= MAX_OTP_FAILURES:
                self._failures[remote_ip] = (count, now + OTP_LOCK_SECONDS)
                return OTP_LOCK_SECONDS
            self._failures[remote_ip] = (count, 0.0)
        return None

    def _verify_otp_code(self, code: str) -> bool:
        clean = str(code or "").strip()
        if not clean:
            return False
        with self._lock:
            if time.time() > self._otp_expires_at:
                return False
            expected = self._otp
        return bool(expected) and hmac.compare_digest(clean, expected)

    def _issue_lan_session(self, remote_ip: str, user_agent: str) -> str:
        sid = secrets.token_urlsafe(24)
        with self._lock:
            self._failures.pop(remote_ip, None)
            self._sessions[sid] = {"ip": remote_ip, "ua": user_agent[:120], "created_at": time.time()}
        return self._serializer().dumps(sid)

    async def _handle_pair(
        self,
        method: str,
        query: str,
        headers: List[tuple[str, str]],
        body_tail: bytes,
        reader: asyncio.StreamReader,
        remote_ip: str,
        wants_json: bool,
    ) -> bytes:
        lock_left = self._check_rate_lock(remote_ip)
        if lock_left:
            if wants_json:
                return _http_response(
                    429, "Too Many Requests",
                    json.dumps({"success": False, "message": "Too many failed pairing attempts."}).encode("utf-8"),
                    "application/json",
                    [("Retry-After", str(lock_left))],
                )
            return _http_response(
                429, "Too Many Requests",
                _pair_html(error_msg=f"Too many attempts. Try again in {lock_left}s."),
                "text/html; charset=utf-8",
                [("Retry-After", str(lock_left))],
            )

        code = ""
        if method == "GET":
            qs = parse_qs(query, keep_blank_values=False)
            code = (qs.get("code") or [""])[0]
            if not code:
                if wants_json:
                    return _http_response(
                        401, "Unauthorized",
                        json.dumps({"success": False, "message": "Pairing code required."}).encode("utf-8"),
                        "application/json",
                    )
                return _http_response(200, "OK", _pair_html(), "text/html; charset=utf-8")
        elif method == "POST":
            content_len = 0
            ctype = ""
            for k, v in headers:
                if k.lower() == "content-length":
                    try:
                        content_len = int(v)
                    except ValueError:
                        content_len = 0
                elif k.lower() == "content-type":
                    ctype = v.lower()
            if content_len > MAX_PAIR_BODY_BYTES:
                return _http_response(413, "Payload Too Large", b"Payload too large")
            need = max(0, content_len - len(body_tail))
            extra = await reader.readexactly(need) if need > 0 else b""
            raw_body = (body_tail + extra)[:MAX_PAIR_BODY_BYTES].decode("utf-8", errors="replace")
            if "application/json" in ctype:
                try:
                    parsed = json.loads(raw_body or "{}")
                    if isinstance(parsed, dict):
                        code = str(parsed.get("code") or "")
                except Exception:
                    code = ""
            else:
                qs = parse_qs(raw_body, keep_blank_values=False)
                code = (qs.get("code") or [""])[0]
        else:
            return _http_response(405, "Method Not Allowed", b"Method not allowed")

        if not self._verify_otp_code(code):
            locked = self._record_failure(remote_ip)
            status = 429 if locked else 401
            reason = "Too Many Requests" if locked else "Unauthorized"
            msg = f"Too many attempts. Locked for {locked}s." if locked else "Invalid or expired pairing code."
            if wants_json:
                return _http_response(
                    status, reason,
                    json.dumps({"success": False, "message": msg}).encode("utf-8"),
                    "application/json",
                )
            return _http_response(status, reason, _pair_html(error_msg=msg), "text/html; charset=utf-8")

        ua = next((v for k, v in headers if k.lower() == "user-agent"), "")
        token = self._issue_lan_session(remote_ip, ua)
        cookie_val = (
            f"{LAN_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={LAN_SESSION_MAX_AGE}"
        )
        if wants_json:
            return _http_response(
                200, "OK",
                json.dumps({"success": True, "paired": True, "ip": remote_ip}).encode("utf-8"),
                "application/json",
                [("Set-Cookie", cookie_val)],
            )
        return _http_response(
            303, "See Other", b"",
            "text/plain; charset=utf-8",
            [("Location", "/"), ("Set-Cookie", cookie_val)],
        )

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        up_writer: Optional[asyncio.StreamWriter] = None
        try:
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=10.0)
                if not chunk:
                    return
                buf += chunk
                if len(buf) > MAX_HEADER_BYTES:
                    writer.write(_http_response(431, "Request Header Fields Too Large", b"Headers too large"))
                    await writer.drain()
                    return

            head_bytes, body_tail = buf.split(b"\r\n\r\n", 1)
            lines = head_bytes.decode("latin-1").split("\r\n")
            if not lines or len(lines[0].split(" ")) < 3:
                writer.write(_http_response(400, "Bad Request", b"Malformed request line"))
                await writer.drain()
                return

            method, raw_target, version = lines[0].split(" ", 2)
            headers: List[tuple[str, str]] = []
            for raw_line in lines[1:]:
                if ":" not in raw_line:
                    continue
                k, v = raw_line.split(":", 1)
                headers.append((k.strip(), v.strip()))

            peer = writer.get_extra_info("peername")
            remote_ip = _clean_ip(peer[0] if peer else "")
            parts = urlsplit(raw_target)
            path = parts.path or "/"
            lower_headers = {k.lower(): v for k, v in headers}
            is_ws = lower_headers.get("upgrade", "").lower() == "websocket"
            wants_json = (
                "application/json" in lower_headers.get("accept", "").lower()
                or "application/json" in lower_headers.get("content-type", "").lower()
                or path.startswith(("/api/", "/admin/api/"))
            )

            if path == PAIR_PATH:
                resp = await self._handle_pair(
                    method.upper(), parts.query, headers, body_tail, reader, remote_ip, wants_json
                )
                writer.write(resp)
                await writer.drain()
                return

            if path == LOGOUT_PATH and method.upper() == "POST":
                sid = self._verify_cookie(headers)
                if sid:
                    with self._lock:
                        self._sessions.pop(sid, None)
                clear_cookie = f"{LAN_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
                if wants_json:
                    writer.write(_http_response(200, "OK", b'{"success":true}', "application/json", [("Set-Cookie", clear_cookie)]))
                else:
                    writer.write(_http_response(303, "See Other", b"", "text/plain", [("Location", PAIR_PATH), ("Set-Cookie", clear_cookie)]))
                await writer.drain()
                return

            sid = self._verify_cookie(headers)
            if not sid:
                if is_ws:
                    writer.write(_http_response(403, "Forbidden", b"LAN pairing required"))
                elif wants_json:
                    writer.write(_http_response(
                        401, "Unauthorized",
                        json.dumps({"success": False, "message": "LAN pairing required", "pair_url": PAIR_PATH}).encode("utf-8"),
                        "application/json",
                    ))
                else:
                    writer.write(_http_response(303, "See Other", b"", "text/plain", [("Location", PAIR_PATH)]))
                await writer.drain()
                return

            if not self._path_allowed(path):
                writer.write(_http_response(403, "Forbidden", b"Path not allowed on LAN gateway"))
                await writer.drain()
                return

            strip_keys = {
                "x-forwarded-for",
                "x-real-ip",
                "forwarded",
                "x-lila-desktop-token",
                "x-lila-lan",
                "x-lila-lan-ip",
                "x-lila-lan-proxy",
            }
            if not is_ws:
                strip_keys.add("connection")

            forwarded_headers = [(k, v) for k, v in headers if k.lower() not in strip_keys]
            if not is_ws:
                forwarded_headers.append(("Connection", "close"))
            forwarded_headers.extend([
                ("X-Forwarded-For", remote_ip),
                ("X-Real-IP", remote_ip),
                ("X-Lila-Lan", "1"),
                ("X-Lila-Lan-IP", remote_ip),
                ("X-Lila-Lan-Proxy", self.proxy_secret),
                ("X-Lila-Desktop-Token", self.desktop_token),
            ])

            up_reader, up_writer = await asyncio.open_connection("127.0.0.1", self.target_port)
            rewritten_head = (
                f"{method} {raw_target} {version}\r\n"
                + "".join(f"{k}: {v}\r\n" for k, v in forwarded_headers)
                + "\r\n"
            ).encode("latin-1")
            up_writer.write(rewritten_head)
            if body_tail:
                up_writer.write(body_tail)
            await up_writer.drain()

            if is_ws:
                await asyncio.gather(_pipe(reader, up_writer), _pipe(up_reader, writer))
                return

            # Forward any remaining fixed Content-Length request body before streaming response
            content_len = 0
            if "content-length" in lower_headers:
                try:
                    content_len = max(0, int(lower_headers["content-length"]))
                except ValueError:
                    content_len = 0
            remaining_body = max(0, content_len - len(body_tail))
            while remaining_body > 0:
                chunk = await asyncio.wait_for(reader.read(min(65_536, remaining_body)), timeout=15.0)
                if not chunk:
                    break
                up_writer.write(chunk)
                await up_writer.drain()
                remaining_body -= len(chunk)

            await _pipe(up_reader, writer)
        except Exception:
            pass
        finally:
            for w in (up_writer, writer):
                if w is not None:
                    try:
                        if not w.is_closing():
                            w.close()
                    except Exception:
                        pass


def set_desktop_local_port(port: int) -> None:
    global _LOCAL_PORT
    with _STATE_LOCK:
        _LOCAL_PORT = int(port or 0)


def get_desktop_local_port() -> int:
    with _STATE_LOCK:
        return _LOCAL_PORT


def start_lan_gateway(
    port: Optional[int] = None,
    otp_ttl: Optional[int] = None,
    allow: Optional[Sequence[str]] = None,
    deny: Optional[Sequence[str]] = None,
    target_port: Optional[int] = None,
) -> dict:
    global _ACTIVE_GATEWAY
    with _STATE_LOCK:
        if _ACTIVE_GATEWAY is not None and _ACTIVE_GATEWAY.is_running:
            return _ACTIVE_GATEWAY.status()
        local_port = int(target_port or _LOCAL_PORT or 0)
        if local_port <= 0:
            raise RuntimeError("Local desktop server port is not active")
        resolved_port = int(port if port is not None else ENV_CONFIG.get_int("DESKTOP_LAN_PORT", 0))
        resolved_ttl = int(otp_ttl if otp_ttl is not None else ENV_CONFIG.get_int("DESKTOP_LAN_OTP_TTL", DEFAULT_OTP_TTL))
        gw = DesktopLanGateway(
            target_port=local_port,
            lan_port=resolved_port,
            otp_ttl=resolved_ttl,
            allow=allow,
            deny=deny,
        )
        _ACTIVE_GATEWAY = gw
    return gw.start()


def stop_lan_gateway() -> dict:
    global _ACTIVE_GATEWAY
    with _STATE_LOCK:
        gw = _ACTIVE_GATEWAY
        _ACTIVE_GATEWAY = None
    if gw is not None:
        gw.stop()
    return {"running": False, "host_ip": detect_lan_ip(), "port": 0}


def lan_status() -> dict:
    with _STATE_LOCK:
        gw = _ACTIVE_GATEWAY
    if gw is not None and gw.is_running:
        return gw.status()
    return {
        "running": False,
        "host_ip": detect_lan_ip(),
        "port": 0,
        "url": "",
        "pair_url": "",
        "otp": "",
        "otp_expires_in": 0,
        "active_sessions": 0,
        "allow": _split_patterns(ENV_CONFIG.get("DESKTOP_LAN_ALLOW", "")),
        "deny": _split_patterns(ENV_CONFIG.get("DESKTOP_LAN_DENY", "")),
    }


def rotate_lan_otp(ttl: Optional[int] = None) -> dict:
    with _STATE_LOCK:
        gw = _ACTIVE_GATEWAY
    if gw is None or not gw.is_running:
        return lan_status()
    return gw.rotate_otp(ttl=ttl)


def revoke_lan_sessions() -> dict:
    with _STATE_LOCK:
        gw = _ACTIVE_GATEWAY
    if gw is None or not gw.is_running:
        return {"revoked": 0, **lan_status()}
    revoked = gw.revoke_sessions()
    return {"revoked": revoked, **gw.status()}
