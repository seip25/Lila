"""
English: Configuration engine for the Lila Framework.
         Provides the built-in field schema, .env loading, type casting,
         production caching, and ENV_CONFIG dict-proxy for user-defined variables.
         This module ships with the framework package — end users do not edit it.
Español: Motor de configuración para el Lila Framework.
         Provee el schema de campos built-in, carga de .env, casteo de tipos,
         caché en producción, y proxy dict ENV_CONFIG para variables del usuario.
         Este módulo viene con el paquete del framework — los usuarios finales no lo editan.
"""

import os
from os import getenv, path


# ──────────────────────────────────────────────────────────────────────────────
# English: Framework built-in field definitions. Each tuple is (key, type, default).
#          These define every .env variable the framework recognizes.
#          The loader, cache reader, cache writer, and module exports are all
#          auto-generated from this single list — zero duplication.
# Español: Definiciones de campos built-in del framework. Cada tupla es (key, tipo, default).
#          Estos definen cada variable .env que el framework reconoce.
#          El loader, lector de caché, escritor de caché, y exports del módulo
#          se auto-generan desde esta única lista — cero duplicación.
# ──────────────────────────────────────────────────────────────────────────────
FRAMEWORK_SCHEMA = [
    # (env_key,              type,   default_value)
    ("SECRET_KEY",           "str",  ""),
    ("PORT",                 "int",  8001),
    ("HOST",                 "str",  "127.0.0.1"),
    ("APP_URL",              "str",  ""),
    ("DEBUG",                "bool", True),
    ("JIT",                  "bool", False),
    ("WORKERS",              "int",  1),
    ("MINIFY_HTML",          "bool", False),
    ("TITLE_PROJECT",        "str",  "Lila project"),
    ("VERSION_PROJECT",      "str",  "1"),
    ("DESCRIPTION_PROJECT",  "str",  ""),
    ("LANG_DEFAULT",         "str",  "en"),
    ("DESCRIPTION_DEFAULT",  "str",  "A Python web framework"),
    ("KEYWORDS_DEFAULT",     "str",  "Python, web, framework"),
    ("AUTHOR_DEFAULT",       "str",  "Seip"),
]


def _cast_value(raw: str, type_name: str):
    """
    English: Casts a raw string value from .env to the appropriate Python type.
    Español: Castea un valor string crudo de .env al tipo Python apropiado.
    """
    if type_name == "bool":
        return raw.lower() in ("true", "1", "yes")
    if type_name == "int":
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0
    return raw


class ConfigLoader:
    """
    English: Loads framework configuration from .env, manages production cache,
             and provides access to any environment variable via ENV_CONFIG.
             The user only needs to edit .env — this class handles everything else.
    Español: Carga la configuración del framework desde .env, gestiona el caché
             de producción, y provee acceso a cualquier variable de entorno via ENV_CONFIG.
             El usuario solo necesita editar .env — esta clase maneja todo lo demás.
    """

    _data: dict = {}
    _all_env: dict = {}
    _loaded: bool = False

    @classmethod
    def load(cls, cache_dir: str = None) -> dict:
        """
        English: Loads all framework configuration. Called once from app/config.py.
                 Returns a dict with all framework fields ready to export.
                 cache_dir: directory where config_cache.py is stored (typically app/).
        Español: Carga toda la configuración del framework. Se llama una vez desde app/config.py.
                 Retorna un dict con todos los campos del framework listos para exportar.
                 cache_dir: directorio donde se almacena config_cache.py (normalmente app/).
        """
        if cls._loaded:
            return dict(cls._data)

        if cache_dir is None:
            cache_dir = os.path.join(os.getcwd(), "app")

        cache_py_path = path.join(cache_dir, "config_cache.py")
        env_path = path.join(os.getcwd(), ".env")

        # English: If DEBUG is set in the OS environment, skip cache entirely.
        # Español: Si DEBUG está configurado en el entorno del SO, saltar el caché completamente.
        env_debug = os.environ.get("DEBUG")
        if env_debug is not None and env_debug.lower() in ("true", "1", "yes"):
            cls._data = cls._read_from_env(cache_py_path, write_cache=False)
            cls._loaded = True
            return dict(cls._data)

        # English: Try loading from production cache if it exists and .env hasn't changed.
        # Español: Intentar cargar desde el caché de producción si existe y .env no cambió.
        if path.exists(cache_py_path):
            env_modified = path.exists(env_path) and os.path.getmtime(env_path) > os.path.getmtime(cache_py_path)
            if not env_modified:
                cached = cls._read_from_cache(cache_py_path)
                if cached is not None:
                    cls._data = cached
                    cls._loaded = True
                    return dict(cls._data)

        # English: Fallback — read from .env and write cache for production.
        # Español: Fallback — leer desde .env y escribir caché para producción.
        cls._data = cls._read_from_env(cache_py_path, write_cache=True)
        cls._loaded = True
        return dict(cls._data)

    @classmethod
    def _read_from_cache(cls, cache_py_path: str) -> dict | None:
        """
        English: Loads configuration from the compiled Python cache file.
                 Returns None if cache is invalid or DEBUG is True.
                 Prioritizes OS environment variables (like those set by Docker).
        Español: Carga la configuración desde el archivo Python de caché compilado.
                 Retorna None si el caché es inválido o DEBUG es True.
                 Prioriza variables de entorno del SO (como las de Docker).
        """
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config_cache", cache_py_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # English: Only use cache when DEBUG is False.
                # Español: Solo usar caché cuando DEBUG es False.
                if getattr(module, "DEBUG", True):
                    return None

                # English: Read all fields from cache using the schema, prioritizing OS environment variables.
                # Español: Leer todos los campos del caché usando el schema, priorizando variables de entorno del SO.
                data = {}
                for key, type_name, default in FRAMEWORK_SCHEMA:
                    env_val = os.environ.get(key)
                    if env_val is not None:
                        data[key] = _cast_value(env_val, type_name)
                    else:
                        data[key] = getattr(module, key, default)
                return data
        except Exception:
            pass
        return None

    @classmethod
    def _read_from_env(cls, cache_py_path: str, write_cache: bool) -> dict:
        """
        English: Reads configuration from .env, casts types using the schema,
                 and optionally writes a production cache file.
        Español: Lee la configuración desde .env, castea tipos usando el schema,
                 y opcionalmente escribe un archivo de caché para producción.
        """
        from dotenv import load_dotenv

        env_path = path.join(os.getcwd(), ".env")
        if path.exists(env_path):
            load_dotenv(dotenv_path=env_path, encoding="utf-8")

        # English: Build data dict by iterating the schema — one loop, zero duplication.
        # Español: Construir el dict de datos iterando el schema — un loop, cero duplicación.
        data = {}
        for key, type_name, default in FRAMEWORK_SCHEMA:
            raw = getenv(key)
            if raw is not None:
                data[key] = _cast_value(raw, type_name)
            else:
                data[key] = default

        # English: Store all raw env values for ENV_CONFIG access to user-defined variables.
        # Español: Almacenar todos los valores crudos del env para acceso via ENV_CONFIG.
        cls._all_env = dict(os.environ)

        # English: Write production cache only if DEBUG is False.
        # Español: Escribir caché de producción solo si DEBUG es False.
        if write_cache and not data.get("DEBUG", True):
            cls._write_cache(cache_py_path, data)

        return data

    @classmethod
    def _write_cache(cls, cache_py_path: str, data: dict) -> None:
        """
        English: Writes configuration cache as a Python file for fast production loading.
                 Auto-generated from the schema — no manual field listing needed.
        Español: Escribe el caché de configuración como archivo Python para carga rápida.
                 Auto-generado desde el schema — sin necesidad de listar campos manualmente.
        """
        try:
            with open(cache_py_path, "w", encoding="utf-8") as f:
                for key, _, _ in FRAMEWORK_SCHEMA:
                    f.write(f"{key} = {repr(data[key])}\n")
        except Exception:
            pass

    @classmethod
    def get(cls, key: str, default=None):
        """
        English: Get any configuration value. Checks framework fields first,
                 then falls back to raw .env / OS environment values.
                 Usage: ConfigLoader.get("MY_CUSTOM_VAR", "fallback")
        Español: Obtiene cualquier valor de configuración. Verifica los campos
                 del framework primero, luego recurre a los valores crudos de .env / entorno.
                 Uso: ConfigLoader.get("MI_VAR_CUSTOM", "fallback")
        """
        if not cls._loaded:
            cls.load()
        if key in cls._data:
            return cls._data[key]
        return cls._all_env.get(key, default)


# ──────────────────────────────────────────────────────────────────────────────
# English: ENV_CONFIG — Dict-like proxy to access any .env or OS environment variable.
#          Usage from anywhere in the project:
#            from lila.core.config import ENV_CONFIG
#            value = ENV_CONFIG["MY_VAR"]
#            value = ENV_CONFIG.get("MY_VAR", "default")
#          No need to register variables — any .env key is accessible.
# Español: ENV_CONFIG — Proxy dict-like para acceder a cualquier variable .env o del entorno.
#          Uso desde cualquier parte del proyecto:
#            from lila.core.config import ENV_CONFIG
#            valor = ENV_CONFIG["MI_VAR"]
#            valor = ENV_CONFIG.get("MI_VAR", "default")
#          No necesita registrar variables — cualquier clave .env es accesible.
# ──────────────────────────────────────────────────────────────────────────────
class _EnvConfigProxy:
    """
    English: Lightweight dict-like proxy that delegates to ConfigLoader.
             Supports [] access, .get(), 'in' operator, and iteration.
    Español: Proxy ligero dict-like que delega a ConfigLoader.
             Soporta acceso [], .get(), operador 'in', e iteración.
    """

    def __getitem__(self, key: str):
        """
        English: Get a config value by key. Raises KeyError if not found.
        Español: Obtiene un valor de configuración por clave. Lanza KeyError si no existe.
        """
        value = ConfigLoader.get(key)
        if value is None:
            raise KeyError(f"Configuration key '{key}' not found in .env or framework defaults")
        return value

    def get(self, key: str, default=None):
        """
        English: Get a config value by key with a fallback default.
        Español: Obtiene un valor de configuración por clave con un default de respaldo.
        """
        return ConfigLoader.get(key, default)

    def __contains__(self, key: str) -> bool:
        """
        English: Check if a key exists in the configuration.
        Español: Verifica si una clave existe en la configuración.
        """
        return ConfigLoader.get(key) is not None

    def __repr__(self) -> str:
        return f"ENV_CONFIG({list(ConfigLoader._data.keys())})"


ENV_CONFIG = _EnvConfigProxy()
