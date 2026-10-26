"""Lila Framework v2.0.0 Configuration Engine.
Loads .env variables, manages schema definitions, PyInstaller desktop paths,
and provides ENV_CONFIG proxy.
"""

import os
import sys
from os import getenv, path
from typing import Any, Optional


FRAMEWORK_SCHEMA = [
    # (env_key,              type,   default_value)
    ("SECRET_KEY",           "str",  ""),
    ("PORT",                 "int",  8000),
    ("HOST",                 "str",  "127.0.0.1"),
    ("APP_URL",              "str",  ""),
    ("DEBUG",                "bool", True),
    ("JIT",                  "bool", False),
    ("WORKERS",              "str",  "1"),
    ("MINIFY_HTML",          "bool", False),
    ("TITLE_PROJECT",        "str",  "Lila Application"),
    ("VERSION_PROJECT",      "str",  "2.0.0"),
    ("DESCRIPTION_PROJECT",  "str",  "Full-stack lightweight Python application"),
    ("LANG_DEFAULT",         "str",  "es"),
    ("DESCRIPTION_DEFAULT",  "str",  "Lila Framework 2.0 Web App"),
    ("KEYWORDS_DEFAULT",     "str",  "python, lila, spa, fast"),
    ("AUTHOR_DEFAULT",       "str",  "Lila Developer"),
    # Cache
    ("CACHE_DRIVER",         "str",  "memory"),
    ("REDIS_HOST",           "str",  "127.0.0.1"),
    ("REDIS_PORT",           "int",  6379),
    ("REDIS_PASSWORD",       "str",  ""),
    ("REDIS_URL",            "str",  ""),
    # AI Providers
    ("OPENAI_API_KEY",       "str",  ""),
    ("OPENAI_MODEL",         "str",  "gpt-6"),
    ("DEEPSEEK_API_KEY",     "str",  ""),
    ("DEEPSEEK_MODEL",       "str",  "deepseek-flash"),
    ("GEMINI_API_KEY",       "str",  ""),
    ("GEMINI_MODEL",         "str",  "gemini-3.8-flash"),
    # Database
    ("DB_TYPE",              "str",  "sqlite"),
    ("DB_NAME",              "str",  "lila"),
    ("DB_DATABASE",          "str",  "lila"),
    ("DB_HOST",              "str",  "127.0.0.1"),
    ("DB_PORT",              "int",  3306),
    ("DB_USER",              "str",  "root"),
    ("DB_PASSWORD",          "str",  ""),
]


def _cast_value(raw: str, type_name: str) -> Any:
    if type_name == "bool":
        return str(raw).strip().lower() in ("true", "1", "yes", "on")
    if type_name == "int":
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            return 0
    return raw


def get_base_path(*subpaths: str) -> str:
    """Returns absolute path respecting PyInstaller sys._MEIPASS for bundled static assets."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = getattr(sys, "_MEIPASS")
    else:
        base = os.getcwd()
    return os.path.join(base, *subpaths) if subpaths else base


def get_data_path(*subpaths: str) -> str:
    """Returns writable directory for databases and logs (current execution dir in desktop mode)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, *subpaths) if subpaths else base


class _EnvConfigProxy:
    """Dictionary proxy for direct access to environment variables with fallback."""
    def get(self, key: str, default: Any = None) -> Any:
        val = os.environ.get(key)
        if val is not None:
            return val
        return default

    def __getitem__(self, key: str) -> Any:
        return os.environ[key]

    def __contains__(self, key: str) -> bool:
        return key in os.environ


ENV_CONFIG = _EnvConfigProxy()


class ConfigLoader:
    _data: dict = {}
    _loaded: bool = False

    @classmethod
    def load(cls, cache_dir: Optional[str] = None) -> dict:
        if cls._loaded:
            return dict(cls._data)

        env_path = os.path.join(get_data_path(), ".env")
        if not os.path.exists(env_path):
            env_path = os.path.join(os.getcwd(), ".env")

        cls._load_dotenv_file(env_path)

        data = {}
        for key, type_name, default in FRAMEWORK_SCHEMA:
            raw = os.environ.get(key)
            if raw is not None:
                data[key] = _cast_value(raw, type_name)
            else:
                data[key] = default
                os.environ[key] = str(default)

        cls._data = data
        cls._loaded = True
        return dict(cls._data)

    @classmethod
    def _load_dotenv_file(cls, filepath: str) -> None:
        if not os.path.exists(filepath):
            return
        try:
            from dotenv import load_dotenv
            load_dotenv(filepath, override=False)
        except ImportError:
            # Simple fallback parser
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass

    @classmethod
    def reload(cls) -> dict:
        cls._loaded = False
        return cls.load()
