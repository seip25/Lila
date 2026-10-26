"""Lila Framework v2.0.0 Lightweight Logger.
Logs events and HTTP requests cleanly without consuming ASGI request streams.
"""

import os
import datetime
import traceback
import re
from typing import Optional
from lila.core.config import get_data_path

DEFAULT_LOG_DIR = os.path.join(get_data_path(), "app", "logs")


def _get_log_dir() -> str:
    path_ = os.environ.get("LILA_LOG_DIR", DEFAULT_LOG_DIR)
    os.makedirs(path_, exist_ok=True)
    return path_


def _get_log_filepath(log_type: str = "app") -> str:
    base = _get_log_dir()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(base, date_str)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{log_type}.log")


class Logger:
    @classmethod
    def _write(cls, log_type: str, message: str) -> None:
        try:
            filepath = _get_log_filepath(log_type)
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [{log_type.upper()}] {message}\n")
        except Exception:
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
        """Formats request log line compactly without consuming ASGI body stream."""
        q_str = f"?{query}" if query else ""
        return (
            f'{client_ip} - "{method} {path}{q_str}" {status_code} '
            f"({duration_ms:.2f}ms) | UA: {user_agent[:100]}"
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


def delete_old_logs(days: int = 30) -> int:
    """Deletes log folders older than the given days."""
    base = _get_log_dir()
    if not os.path.exists(base):
        return 0
    now = datetime.datetime.now()
    cutoff = datetime.timedelta(days=days)
    deleted_count = 0

    for name in os.listdir(base):
        target = os.path.join(base, name)
        if not os.path.isdir(target):
            continue
        try:
            folder_date = datetime.datetime.strptime(name, "%Y-%m-%d")
            if (now - folder_date) > cutoff:
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
        except ValueError:
            continue

    return deleted_count
