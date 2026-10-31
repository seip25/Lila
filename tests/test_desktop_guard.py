import os
import unittest

from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.routing import Router
from lila.core.request import Request


class DesktopGuardTests(unittest.TestCase):
    def test_desktop_token_sets_cookie_and_blocks_others(self):
        router = Router()

        @router.get("/")
        async def home(request: Request):
            return {"ok": True}

        old = os.environ.get("LILA_DESKTOP_TOKEN")
        os.environ["LILA_DESKTOP_TOKEN"] = "desktop-test-token"
        try:
            app = App(routes=[router], debug=False, openapi=False)
            client = TestClient(app)
            self.assertEqual(client.get("/").status_code, 403)
            self.assertEqual(client.get("/", params={"_dt": "wrong"}).status_code, 403)

            redirect = client.get("/", params={"_dt": "desktop-test-token"}, follow_redirects=False)
            self.assertEqual(redirect.status_code, 303)
            self.assertEqual(redirect.headers.get("location"), "/")
            self.assertIn("lila_desktop", redirect.cookies)

            # TestClient persists the Set-Cookie from the redirect.
            self.assertEqual(client.get("/").status_code, 200)
        finally:
            if old is None:
                os.environ.pop("LILA_DESKTOP_TOKEN", None)
            else:
                os.environ["LILA_DESKTOP_TOKEN"] = old


if __name__ == "__main__":
    unittest.main()
