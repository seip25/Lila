import os
import shutil
import uuid
import unittest

from itsdangerous import BadSignature, URLSafeTimedSerializer


class SecretTests(unittest.TestCase):
    def test_empty_secret_is_never_used(self):
        from lila.core import config as config_module

        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_secret")
        work = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(work, exist_ok=True)
        old_cwd = os.getcwd()
        old_secret = os.environ.get("SECRET_KEY")
        try:
            os.chdir(work)
            os.environ["SECRET_KEY"] = ""
            config_module._SECRET_CACHE = None
            secret = config_module.get_secret_key()
            self.assertGreaterEqual(len(secret), 32)

            from lila.core.session import _get_session_serializer

            forged = URLSafeTimedSerializer("", salt="lila-session-salt").dumps(
                '{"user_id": 1, "email": "admin@example.com"}'
            )
            with self.assertRaises(BadSignature):
                _get_session_serializer().loads(forged)
        finally:
            os.chdir(old_cwd)
            if old_secret is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = old_secret
            config_module._SECRET_CACHE = None
            shutil.rmtree(root, ignore_errors=True)


class ServerLoggingTests(unittest.TestCase):
    def setUp(self):
        from lila.core import config as config_module

        self._saved_env = {k: os.environ.get(k) for k in ("DEBUG", "LILA_ACCESS_LOG", "LILA_LOG_LEVEL")}
        self._saved_loaded = config_module.ConfigLoader._loaded
        self._saved_data = dict(config_module.ConfigLoader._data)

    def tearDown(self):
        from lila.core import config as config_module

        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        config_module.ConfigLoader._loaded = self._saved_loaded
        config_module.ConfigLoader._data = self._saved_data

    def test_server_logging_options_defaults_and_overrides(self):
        from lila.core.config import ConfigLoader, server_logging_options

        ConfigLoader._loaded = True
        ConfigLoader._data = {"DEBUG": False, "LILA_ACCESS_LOG": False, "LILA_LOG_LEVEL": ""}
        self.assertEqual(server_logging_options(), (False, "warning"))
        self.assertEqual(server_logging_options(debug=True), (True, "info"))
        self.assertEqual(server_logging_options(debug=False, access_log=True, log_level="error"), (True, "error"))

        ConfigLoader._data = {"DEBUG": False, "LILA_ACCESS_LOG": True, "LILA_LOG_LEVEL": "info"}
        self.assertEqual(server_logging_options(), (True, "info"))

    def test_app_silences_uvicorn_loggers_when_debug_false(self):
        import logging
        from lila.core.app import App
        from lila.core.config import ConfigLoader

        ConfigLoader._loaded = True
        ConfigLoader._data = {"DEBUG": False, "LILA_ACCESS_LOG": False, "LILA_LOG_LEVEL": ""}

        access = logging.getLogger("uvicorn.access")
        err = logging.getLogger("uvicorn.error")
        dummy = logging.NullHandler()
        access.handlers = [dummy]
        access.propagate = True
        err.setLevel(logging.INFO)
        try:
            App(debug=False)
            self.assertFalse(access.hasHandlers())
            self.assertFalse(access.propagate)
            self.assertEqual(err.level, logging.WARNING)
        finally:
            access.handlers = []
            access.propagate = True
            err.setLevel(logging.NOTSET)

    def test_cli_run_passes_quiet_logging_when_debug_false(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from lila.cli import main as cli_main
        from lila.core.config import ConfigLoader

        captured = {}

        def fake_run(app_str, **kwargs):
            captured["app"] = app_str
            captured.update(kwargs)

        ConfigLoader._loaded = True
        ConfigLoader._data = {
            "DEBUG": False,
            "HOST": "127.0.0.1",
            "PORT": 8000,
            "CACHE_DRIVER": "memory",
            "LILA_SERVER": "uvicorn",
            "LILA_ACCESS_LOG": False,
            "LILA_LOG_LEVEL": "",
        }
        with patch("os.path.exists", return_value=True), patch.dict(
            sys.modules, {"uvicorn": SimpleNamespace(run=fake_run)}
        ):
            cli_main.run(
                host="127.0.0.1",
                port=8000,
                workers=1,
                proxy_headers=True,
                forwarded_allow_ips="127.0.0.1",
                server="uvicorn",
                max_rss=0,
                access_log=None,
                log_level="",
            )
        self.assertIs(captured["access_log"], False)
        self.assertEqual(captured["log_level"], "warning")


if __name__ == "__main__":
    unittest.main()
