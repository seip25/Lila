"""
Configuration engine for Lila Framework.
Provides schema validation, .env loading, type casting, production bytecode caching, and ENV_CONFIG proxy.
"""

import os
from os import getenv, path

FRAMEWORK_SCHEMA = [
    # (env_key,              type,   default_value)
    ("SECRET_KEY",           "str",  ""),
    ("PORT",                 "int",  8000),
    ("HOST",                 "str",  "127.0.0.1"),
    ("APP_URL",              "str",  ""),
    ("DEBUG",                "bool", True),
    ("JIT",                  "bool", False),
    ("WORKERS",              "str",  "2"),
    ("TITLE_PROJECT",        "str",  "Lila project"),
    ("VERSION_PROJECT",      "str",  "1.0.0"),
    ("DESCRIPTION_PROJECT",  "str",  ""),
    ("LANG_DEFAULT",         "str",  "en"),
    ("DESCRIPTION_DEFAULT",  "str",  "A high-performance Python web framework"),
    ("KEYWORDS_DEFAULT",     "str",  "Python, web, framework, asgi, api"),
    ("AUTHOR_DEFAULT",       "str",  "Lila"),
]


def _cast_value(raw: str, type_name: str):
    """Casts raw string values from .env to appropriate Python types."""
    if type_name == "bool":
        return raw.lower() in ("true", "1", "yes")
    if type_name == "int":
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0
    return raw


class ConfigLoader:
    """Loads framework configuration from .env, manages cache, and proxies environment variables."""

    _data: dict = {}
    _all_env: dict = {}
    _loaded: bool = False

    @classmethod
    def load(cls, cache_dir: str = None) -> dict:
        """Loads all framework configuration into a dictionary."""
        if cls._loaded:
            return dict(cls._data)

        if cache_dir is None:
            cache_dir = os.path.join(os.getcwd(), "app", "cache")

        cache_py_path = path.join(cache_dir, "config_cache.py")
        legacy_cache_py_path = path.join(os.getcwd(), "app", "config_cache.py")
        env_path = path.join(os.getcwd(), ".env")

        env_debug = os.environ.get("DEBUG")
        if env_debug is not None and env_debug.lower() in ("true", "1", "yes"):
            cls._data = cls._read_from_env(cache_py_path, write_cache=False)
            cls._loaded = True
            return dict(cls._data)

        target_cache = cache_py_path if path.exists(cache_py_path) else (legacy_cache_py_path if path.exists(legacy_cache_py_path) else None)
        if target_cache:
            env_modified = path.exists(env_path) and os.path.getmtime(env_path) > os.path.getmtime(target_cache)
            if not env_modified:
                cached = cls._read_from_cache(target_cache)
                if cached is not None:
                    cls._data = cached
                    cls._loaded = True
                    return dict(cls._data)

        cls._data = cls._read_from_env(cache_py_path, write_cache=True)
        cls._loaded = True
        return dict(cls._data)

    @classmethod
    def _read_from_cache(cls, cache_py_path: str) -> dict | None:
        """Loads configuration from the cached Python file in production."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config_cache", cache_py_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if getattr(module, "DEBUG", True):
                    return None

                data = {}
                for key, type_name, default in FRAMEWORK_SCHEMA:
                    env_val = os.environ.get(key)
                    if env_val is not None:
                        data[key] = _cast_value(env_val, type_name)
                    else:
                        data[key] = getattr(module, key, default)
                cls._all_env = dict(os.environ)
                return data
        except Exception:
            pass
        return None

    @classmethod
    def _read_from_env(cls, cache_py_path: str, write_cache: bool) -> dict:
        """Reads configuration from .env and writes production cache if DEBUG=False."""
        from dotenv import load_dotenv

        env_path = path.join(os.getcwd(), ".env")
        if path.exists(env_path):
            load_dotenv(dotenv_path=env_path, encoding="utf-8")

        data = {}
        for key, type_name, default in FRAMEWORK_SCHEMA:
            raw = getenv(key)
            if raw is not None:
                data[key] = _cast_value(raw, type_name)
            else:
                data[key] = default

        cls._all_env = dict(os.environ)

        if write_cache and not data.get("DEBUG", True):
            cls._write_cache(cache_py_path, data)

        return data

    @classmethod
    def _write_cache(cls, cache_py_path: str, data: dict) -> None:
        """Writes configuration cache file in app/cache/."""
        try:
            parent_dir = os.path.dirname(cache_py_path)
            os.makedirs(parent_dir, exist_ok=True)
            init_file = os.path.join(parent_dir, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, "w", encoding="utf-8") as f:
                    f.write("# Lila app cache package\n")

            with open(cache_py_path, "w", encoding="utf-8") as f:
                for key, _, _ in FRAMEWORK_SCHEMA:
                    f.write(f"{key} = {repr(data[key])}\n")
        except Exception:
            pass

    @classmethod
    def get(cls, key: str, default=None):
        """Get any configuration value from schema, .env, or OS environment."""
        if not cls._loaded:
            cls.load()
        if key in cls._data:
            return cls._data[key]
        return cls._all_env.get(key, os.environ.get(key, default))


class _EnvConfigProxy:
    """Proxy dictionary allowing bracket and .get access to environment settings."""

    def __getitem__(self, key: str):
        value = ConfigLoader.get(key)
        if value is None:
            raise KeyError(f"Configuration key '{key}' not found")
        return value

    def get(self, key: str, default=None):
        return ConfigLoader.get(key, default)

    def __contains__(self, key: str) -> bool:
        return ConfigLoader.get(key) is not None

    def __repr__(self) -> str:
        return f"ENV_CONFIG({list(ConfigLoader._data.keys())})"


ENV_CONFIG = _EnvConfigProxy()
