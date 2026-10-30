"""Lila Framework v2.0.x Lightweight Logger.

Buffered, stream-safe logging without opening/closing a file per request.
Log folders are date-based (``app/logs/YYYY-MM-DD/type.log``) and can be
cleaned programmatically.
"""

import os
import datetime
import traceback
import threading
from typing import Optional, Dict, Tuple, TextIO
from urllib.parse import parse_qsl, urlencode

from lila.core.config import get_data_path

_SENSITIVE_QUERY = frozenset(
    {"token", "access_token", "refresh_token", "key", "api_key", "password", "secret", "csrf", "_csrf", "code"}
)


def _redact_query(query: str) -> str:
    if not query:
        return ""
    try:
        pairs = [(k, "***" if k.lower() in _SENSITIVE_QUERY else v) for k, v in parse_qsl(query, keep_blank_values=True)]
        return urlencode(pairs, doseq=True)
    except Exception:
        return query


DEFAULT_LOG_DIR = os.path.join(get_data_path(), "app", "logs")

_lock = threading.RLock()
_handles: Dict[Tuple[str, str], TextIO] = {}
_current_date: Optional[str] = None
_created_dirs: set = set()


def _get_log_dir() -> str:
    configured = os.environ.get("LILA_LOG_DIR") or DEFAULT_LOG_DIR
    if not os.path.isabs(configured):
        configured = os.path.join(os.getcwd(), configured)
    if configured not in _created_dirs:
        os.makedirs(configured, exist_ok=True)
        _created_dirs.add(configured)
    return configured


def _get_log_filepath(log_type: str = "app") -> str:
    base = _get_log_dir()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(base, date_str)
    if folder not in _created_dirs:
        os.makedirs(folder, exist_ok=True)
        _created_dirs.add(folder)
    return os.path.join(folder, f"{log_type}.log")


def _close_handles() -> None:
    for handle in list(_handles.values()):
        try:
            handle.flush()
            handle.close()
        except Exception:
            pass
    _handles.clear()


class Logger:
    @classmethod
    def _write(cls, log_type: str, message: str) -> None:
        global _current_date
        try:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            with _lock:
                if _current_date != date_str:
                    _close_handles()
                    _current_date = date_str
                key = (log_type, date_str)
                handle = _handles.get(key)
                if handle is None:
                    filepath = _get_log_filepath(log_type)
                    handle = open(filepath, "a", encoding="utf-8", buffering=1)
                    _handles[key] = handle
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                handle.write(f"[{ts}] [{log_type.upper()}] {message}\n")
        except Exception:
            # Logging must never break a request.
            pass

    @classmethod
    def info(cls, message: str) -> None:
        cls._write("info", message)

    @classmethod
    def warning(cls, message: str) -> None:
        cls._write("warning", message)

    @classmethod
    def error(cls, message: str, exception: Optional[Exception] = None) -> None:
        if exception:
            message = f"{message}\n{traceback.format_exc()}"
        cls._write("error", message)

    @classmethod
    def log(cls, log_type: str, message: str) -> None:
        cls._write(log_type, message)

    @classmethod
    def format_request(
        cls,
        client_ip: str,
        method: str,
        path: str,
        query: str = "",
        status_code: int = 200,
        duration_ms: float = 0.0,
        user_agent: str = "",
    ) -> str:
        """Formats a compact request log line."""
        q_str = f"?{_redact_query(query)}" if query else ""
        safe_ua = user_agent.replace("\r", "").replace("\n", " ")[:100]
        return (
            f'{client_ip} - "{method} {path}{q_str}" {status_code} '
            f"({duration_ms:.2f}ms) | UA: {safe_ua}"
        )

    @classmethod
    def log_request(
        cls,
        client_ip: str,
        method: str,
        path: str,
        query: str = "",
        status_code: int = 200,
        duration_ms: float = 0.0,
        user_agent: str = "",
    ) -> None:
        line = cls.format_request(
            client_ip, method, path, query, status_code, duration_ms, user_agent
        )
        cls._write("requests", line)

    @classmethod
    async def request(cls, request) -> str:
        """Returns a safe one-line representation of a Starlette request (v1 helper)."""
        try:
            client = getattr(request, "client", None)
            client_ip = getattr(client, "host", "unknown") if client else "unknown"
            return cls.format_request(
                client_ip=client_ip,
                method=getattr(request, "method", "GET"),
                path=str(getattr(getattr(request, "url", None), "path", "")),
                query=str(getattr(getattr(request, "url", None), "query", "")),
                user_agent=request.headers.get("user-agent", "") if hasattr(request, "headers") else "",
            )
        except Exception:
            return ""


def delete_old_logs(days: int = 30) -> int:
    """Deletes date folders older than ``days``. ``days=0`` clears everything."""
    base = _get_log_dir()
    if not os.path.exists(base):
        return 0
    if days <= 0:
        _close_handles()
    now = datetime.datetime.now()
    cutoff = datetime.timedelta(days=days)
    deleted_count = 0

    for name in os.listdir(base):
        target = os.path.join(base, name)
        if not os.path.isdir(target):
            continue
        try:
            folder_date = datetime.datetime.strptime(name, "%Y-%m-%d")
        except ValueError:
            continue
        age = now - folder_date
        if days > 0 and age <= cutoff:
            continue
        for file_name in os.listdir(target):
            try:
                os.remove(os.path.join(target, file_name))
            except Exception:
                pass
        try:
            os.rmdir(target)
            deleted_count += 1
        except Exception:
            pass

    if days <= 0:
        _close_handles()
    return deleted_count


def clear_logs() -> int:
    """Clears all log files and folders (used by the admin panel)."""
    return delete_old_logs(days=0)
