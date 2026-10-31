import unittest

from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.middleware import login_required, session_active
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.routing import Router
from lila.core.session import Session


class AuthDecoratorTests(unittest.TestCase):
    def test_login_required_reads_real_starlette_request(self):
        router = Router(middlewares=[login_required])

        @router.get("/private")
        async def private(request: Request):
            return {"ok": True}

        @router.get("/private-alias")
        async def private_alias(req: Request):
            return {"ok": True}

        auth_router = Router()

        @auth_router.get("/make-session")
        async def make_session(request: Request):
            response = JSONResponse({"ok": True})
            await Session.set_async({"user_id": 1, "email": "u@example.com"}, response, key="auth")
            return response

        @auth_router.get("/guest")
        @session_active
        async def guest(request: Request):
            return {"guest": True}

        app = App(routes=[router, auth_router], debug=False, openapi=False)
        client = TestClient(app)

        login = client.get("/make-session")
        session_cookie = login.cookies.get("auth")
        self.assertTrue(session_cookie)

        response = client.get("/private", cookies={"auth": session_cookie})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        alias = client.get("/private-alias", cookies={"auth": session_cookie})
        self.assertEqual(alias.status_code, 200)
        self.assertTrue(alias.json()["ok"])

        guest = client.get("/guest", cookies={"auth": session_cookie}, follow_redirects=False)
        self.assertEqual(guest.status_code, 303)
        self.assertEqual(guest.headers["location"], "/dashboard")


if __name__ == "__main__":
    unittest.main()
