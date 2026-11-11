import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.testclient import TestClient

from lila.core import app as app_module
from lila.core.app import App, register_lifecycle


class LifecycleTests(unittest.TestCase):
    def test_registered_hooks_run_on_startup_and_shutdown(self):
        calls = []

        async def start(app):
            calls.append("start")

        def stop(app):
            calls.append("stop")

        register_lifecycle(start, stop)
        try:
            with TestClient(App(routes=[], debug=False)):
                self.assertEqual(calls, ["start"])
            self.assertEqual(calls, ["start", "stop"])
        finally:
            app_module._STARTUP_HOOKS.remove(start)
            app_module._SHUTDOWN_HOOKS.remove(stop)


if __name__ == "__main__":
    unittest.main()
