"""Lila Framework v2.0.x Configuration Engine.

Loads .env variables, provides a typed ENV_CONFIG proxy, manages PyInstaller
desktop paths, validates the SECRET_KEY and exposes safe defaults.

Key guarantees:
- ``ENV_CONFIG.get("DEBUG")`` returns a bool when the framework schema knows the key.
- An empty or placeholder ``SECRET_KEY`` can never be used to sign sessions/CSRF.
- ``ConfigLoader.load()`` has no side effects on ``os.environ``.
"""

import os
import sys
import secrets
from typing import Any, Optional


FRAMEWORK_SCHEMA = [
    # (env_key,              type,   default_value)
    ("SECRET_KEY",           "str",  ""),
    ("APP_ENV",              "str",  "development"),
    ("PORT",                 "int",  8000),
    ("HOST",                 "str",  "127.0.0.1"),
    ("APP_URL",              "str",  ""),
    ("DEBUG",                "bool", False),
    ("WORKERS",              "str",  "1"),
    ("TITLE_PROJECT",        "str",  "Lila Application"),
    ("VERSION_PROJECT",      "str",  "2.0"),
    ("DESCRIPTION_PROJECT",  "str",  "Full-stack lightweight Python application"),
    ("LANG_DEFAULT",         "str",  "es"),
    ("DESCRIPTION_DEFAULT",  "str",  "Lila Framework 2.0 Web App"),
    ("KEYWORDS_DEFAULT",     "str",  "python, lila, spa, fast"),
    ("AUTHOR_DEFAULT",       "str",  "Lila Developer"),
    # Cache
    ("CACHE_DRIVER",         "str",  "memory"),
    ("CACHE_DIR",            "str",  "app/cache/data"),
    ("CACHE_MAX_ITEMS",      "int",  10000),
    ("CACHE_DEFAULT_TTL",    "int",  300),
    ("MODEL_CACHE_TTL",      "int",  5),
    ("REDIS_HOST",           "str",  "127.0.0.1"),
    ("REDIS_PORT",           "int",  6379),
    ("REDIS_PASSWORD",       "str",  ""),
    ("REDIS_URL",            "str",  ""),
    # Static
    ("STATIC_CACHE_MAX_AGE", "int",  86400),
    # Logging
    ("LILA_LOG_DIR",         "str",  ""),
    # AI Providers
    ("OPENAI_API_KEY",       "str",  ""),
    ("OPENAI_MODEL",         "str",  "gpt-4o-mini"),
    ("DEEPSEEK_API_KEY",     "str",  ""),
    ("DEEPSEEK_MODEL",       "str",  "deepseek-chat"),
    ("GEMINI_API_KEY",       "str",  ""),
    ("GEMINI_MODEL",         "str",  "gemini-2.0-flash"),
    # Database
    ("DB_TYPE",              "str",  "sqlite"),
    ("DB_NAME",              "str",  "lila"),
    ("DB_DATABASE",          "str",  "lila"),
    ("DB_HOST",              "str",  "127.0.0.1"),
    ("DB_PORT",              "int",  0),
    ("DB_USER",              "str",  "root"),
    ("DB_PASSWORD",          "str",  ""),
    # Mailer
    ("SMTP_HOST",            "str",  "127.0.0.1"),
    ("SMTP_PORT",            "int",  587),
    ("SMTP_USER",            "str",  ""),
    ("SMTP_PASSWORD",        "str",  ""),
    ("SMTP_TLS",             "bool", True),
    ("SMTP_SSL",             "bool", False),
    ("SMTP_FROM",            "str",  "noreply@lila.local"),
    # OAuth
    ("GOOGLE_CLIENT_ID",     "str",  ""),
    ("GOOGLE_CLIENT_SECRET", "str",  ""),
    ("GITHUB_CLIENT_ID",     "str",  ""),
    ("GITHUB_CLIENT_SECRET", "str",  ""),
    ("DISCORD_CLIENT_ID",    "str",  ""),
    ("DISCORD_CLIENT_SECRET", "str", ""),
]

# Defaults that must never be accepted as a real signing key.
_PLACEHOLDER_SECRET_MARKERS = (
    "change_me",
    "change-me",
    "your-secret",
    "your_secret",
    "your-64",
    "lila-session-secret",
    "lila-auth-secret",
    "lila-fallback-secret",
    "supersecret",
    "secret-key-here",
)

_SECRET_CACHE: Optional[str] = None
_SECRET_WARNED = False


def _cast_value(raw: str, type_name: str) -> Any:
    if type_name == "bool":
        if isinstance(raw, bool):
            return raw
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
    """Returns writable directory for databases, cache and logs."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, *subpaths) if subpaths else base


def _is_placeholder_secret(value: str) -> bool:
    clean = (value or "").strip().lower()
    if not clean:
        return True
    return any(marker in clean for marker in _PLACEHOLDER_SECRET_MARKERS)


def _read_secret_file(filepath: str) -> Optional[str]:
    try:
        if os.path.isfile(filepath):
            with open(filepath, "r", encoding="utf-8") as fh:
                value = fh.read().strip()
            if value and not _is_placeholder_secret(value):
                return value
    except Exception:
        pass
    return None


def _write_secret_file(filepath: str, value: str) -> bool:
    """Atomically creates the secret file. Returns False if another process won the race."""
    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        fd = os.open(filepath, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(value)
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def get_secret_key() -> str:
    """Returns a strong SECRET_KEY, generating a persisted one if necessary.

    This is the only supported way to obtain the signing key. It prevents the
    catastrophic case where sessions/CSRF were signed with an empty key.
    """
    global _SECRET_CACHE, _SECRET_WARNED
    if _SECRET_CACHE:
        return _SECRET_CACHE

    raw = str(os.environ.get("SECRET_KEY", "") or "").strip()
    if raw and not _is_placeholder_secret(raw) and len(raw) >= 16:
        if len(raw) < 32:
            _warn_once("[Lila] SECRET_KEY is shorter than 32 chars; consider rotating it with 'lila secret-key'.")
        _SECRET_CACHE = raw
        return raw

    # Try the persisted dev/prod secret next to the app.
    filepath = os.environ.get("LILA_SECRET_FILE") or get_data_path(".lila_secret")
    persisted = _read_secret_file(filepath)
    if persisted:
        os.environ["SECRET_KEY"] = persisted
        _SECRET_CACHE = persisted
        _warn_once(
            "[Lila] No valid SECRET_KEY in .env. Using the persisted key in "
            f"'{filepath}'. Set SECRET_KEY in .env for production deployments."
        )
        return persisted

    generated = secrets.token_urlsafe(48)
    if not _write_secret_file(filepath, generated):
        # Another worker created it first; use its value.
        persisted = _read_secret_file(filepath)
        if persisted:
            os.environ["SECRET_KEY"] = persisted
            _SECRET_CACHE = persisted
            return persisted
        # Last resort: never fall back to an empty/known key.
        _SECRET_CACHE = generated
        os.environ["SECRET_KEY"] = generated
        _warn_once(
            "[Lila] Could not persist a SECRET_KEY. Generated a temporary one; "
            "sessions will not survive a restart. Set SECRET_KEY in .env."
        )
        return generated

    os.environ["SECRET_KEY"] = generated
    _SECRET_CACHE = generated
    _warn_once(
        f"[Lila] Generated a new SECRET_KEY and stored it in '{filepath}'. "
        "Add SECRET_KEY to .env before deploying to production."
    )
    return generated


def _warn_once(message: str) -> None:
    global _SECRET_WARNED
    if _SECRET_WARNED:
        return
    _SECRET_WARNED = True
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass


class _EnvConfigProxy:
    """Dictionary proxy for environment variables with typed framework defaults."""

    def get(self, key: str, default: Any = None) -> Any:
        # Once ConfigLoader ran, schema keys are returned with their real type.
        if ConfigLoader._loaded and key in ConfigLoader._data:
            value = ConfigLoader._data[key]
            return default if value is None else value
        val = os.environ.get(key)
        if val is not None:
            return val
        return default

    def __getitem__(self, key: str) -> Any:
        if ConfigLoader._loaded and key in ConfigLoader._data:
            return ConfigLoader._data[key]
        return os.environ[key]

    def __contains__(self, key: str) -> bool:
        return (ConfigLoader._loaded and key in ConfigLoader._data) or key in os.environ

    # Typed helpers for code that cannot assume ConfigLoader ran first.
    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, default)
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    def get_list(self, key: str, default: Optional[list] = None, sep: str = ",") -> list:
        value = self.get(key, None)
        if value is None or value == "":
            return list(default or [])
        if isinstance(value, (list, tuple)):
            return list(value)
        return [item.strip() for item in str(value).split(sep) if item.strip()]


ENV_CONFIG = _EnvConfigProxy()


def is_debug() -> bool:
    """Typed DEBUG accessor (avoids ``bool("False") is True``)."""
    if ConfigLoader._loaded and "DEBUG" in ConfigLoader._data:
        return bool(ConfigLoader._data["DEBUG"])
    return ENV_CONFIG.get_bool("DEBUG", False)


class ConfigLoader:
    _data: dict = {}
    _loaded: bool = False

    @classmethod
    def load(cls, cache_dir: Optional[str] = None) -> dict:
        """Loads .env + framework defaults once and returns a typed dict."""
        if cls._loaded:
            return dict(cls._data)

        env_path = os.path.join(get_data_path(), ".env")
        if not os.path.exists(env_path):
            env_path = os.path.join(os.getcwd(), ".env")
        cls._load_dotenv_file(env_path)

        data = {}
        for key, type_name, default in FRAMEWORK_SCHEMA:
            raw = os.environ.get(key)
            if raw is None or raw == "":
                data[key] = default
            else:
                data[key] = _cast_value(raw, type_name)

        # SECRET_KEY is special: an empty value is unsafe. Generate a persistent one.
        data["SECRET_KEY"] = get_secret_key()

        cls._data = data
        cls._loaded = True
        cls._warn_insecure_config(data)
        return dict(cls._data)

    @classmethod
    def _warn_insecure_config(cls, data: dict) -> None:
        warnings = []
        if data.get("DEBUG") and str(data.get("APP_URL", "")).startswith("https://"):
            warnings.append("DEBUG=True with an HTTPS APP_URL. Disable DEBUG in production.")
        if data.get("CACHE_DRIVER") == "redis" and str(data.get("WORKERS", "1")) == "max":
            warnings.append("WORKERS=max with in-process state; ensure Redis is reachable for shared sessions/cache.")
        for message in warnings:
            try:
                print(f"[Lila] {message}", file=sys.stderr)
            except Exception:
                pass

    @classmethod
    def _load_dotenv_file(cls, filepath: str) -> None:
        if not os.path.exists(filepath):
            return
        try:
            from dotenv import load_dotenv
            load_dotenv(filepath, override=False)
        except ImportError:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass

    @classmethod
    def data(cls) -> dict:
        return dict(cls._data)

    @classmethod
    def reload(cls) -> dict:
        global _SECRET_CACHE
        cls._loaded = False
        cls._data = {}
        _SECRET_CACHE = None
        return cls.load()
