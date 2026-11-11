import os
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from jinja2 import ChoiceLoader, DictLoader
from starlette.testclient import TestClient

from lila.core import system_db
from lila.core.app import App
from lila.core.routing import Router
from lila.testing import login


class _TmpData:
    def _start(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"LILA_DATA_DIR": self.tmp})
        self.env.start()
        system_db.close_all()

    def _stop(self):
        system_db.close_all()
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


class PermissionTests(unittest.TestCase):
    def setUp(self):
        from lila.core.permissions import define_roles, require_permission

        define_roles({"admin": ["*"], "editor": ["posts.*"], "user": ["posts.read"]})
        router = Router()

        @router.get("/api/admin", roles=["admin"])
        async def admin_only(request):
            return {"ok": True}

        @router.delete("/api/posts/{id:int}", permissions=["posts.delete"])
        async def delete_post(request, id: int):
            return {"deleted": id}

        @router.get("/reports")
        @require_permission("reports.view")
        async def reports(request):
            return "<p>reports</p>"

        self.client = TestClient(App(routes=[router], debug=False, rate_limit=None))

    def test_roles_and_wildcard_permissions(self):
        self.assertEqual(self.client.get("/api/admin").status_code, 401)
        login(self.client, {"id": 1, "role": "user"})
        self.assertEqual(self.client.get("/api/admin").status_code, 403)
        self.assertEqual(self.client.delete("/api/posts/3").status_code, 403)
        login(self.client, {"id": 2, "roles": ["editor"]})
        self.assertEqual(self.client.delete("/api/posts/3").json(), {"deleted": 3})
        self.assertEqual(self.client.get("/reports").status_code, 403)
        login(self.client, {"id": 3, "role": "admin"})
        self.assertEqual(self.client.get("/api/admin").json(), {"ok": True})
        self.assertEqual(self.client.get("/reports").status_code, 200)

    def test_pages_redirect_to_login(self):
        res = self.client.get("/reports", follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/login")

    def test_jinja_can(self):
        from lila.core.permissions import has_permission

        self.assertTrue(has_permission({"role": "editor"}, "posts.edit"))
        self.assertFalse(has_permission({"role": "user"}, "posts.edit"))
        self.assertTrue(has_permission({"scopes": ["posts.edit"]}, "posts.edit"))


class ApiKeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_verify_scope_and_revoke(self):
        from lila.core.api_keys import ApiKey, ApiKeys
        from lila.core.cache import Cache
        from lila.testing import temp_database

        Cache.configure("memory")
        async with temp_database(ApiKey):
            token, row = await ApiKeys.create_async(7, "CI", scopes=["posts.read"])
            self.assertTrue(token.startswith("lila_"))
            self.assertNotIn("key_hash", row)
            listed = await ApiKeys.list_async(7)
            self.assertEqual(len(listed), 1)
            self.assertNotIn("key_hash", listed[0])

            router = Router()

            @router.get("/api/read", api_key=["posts.read"])
            async def read(request):
                return {"user": request.state.user["id"]}

            @router.get("/api/write", api_key=["posts.write"])
            async def write(request):
                return {"ok": True}

            app = App(routes=[router], debug=False, rate_limit=None)
            async def get(path, headers=None):
                messages = []
                scope = {"type": "http", "method": "GET", "path": path, "raw_path": path.encode(),
                         "query_string": b"", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
                         "client": ("127.0.0.1", 1), "server": ("t", 80), "scheme": "http", "http_version": "1.1",
                         "root_path": ""}

                async def receive():
                    return {"type": "http.request", "body": b"", "more_body": False}

                async def send(message):
                    messages.append(message)

                await app(scope, receive, send)
                status = next(m["status"] for m in messages if m["type"] == "http.response.start")
                body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
                return status, body

            self.assertEqual((await get("/api/read"))[0], 401)
            status, body = await get("/api/read", {"Authorization": f"Bearer {token}"})
            self.assertEqual((status, body), (200, b'{"user":7}'))
            self.assertEqual((await get("/api/read", {"X-API-Key": token}))[0], 200)
            self.assertEqual((await get("/api/write", {"X-API-Key": token}))[0], 403)
            self.assertEqual((await get("/api/read", {"X-API-Key": token + "x"}))[0], 401)
            self.assertTrue(await ApiKeys.revoke_async(row["id"], user_id=7))
            self.assertEqual((await get("/api/read", {"X-API-Key": token}))[0], 401)


class RefreshTokenTests(_TmpData, unittest.TestCase):
    def setUp(self):
        self._start()

    def tearDown(self):
        self._stop()

    def test_rotation_reuse_detection_and_revoke(self):
        from lila.core.auth import JWT

        pair = JWT.issue_pair({"user_id": 5}, access_minutes=5, refresh_days=1)
        self.assertEqual(JWT.decode(pair["access_token"])["typ"], "access")
        second = JWT.refresh(pair["refresh_token"])
        self.assertIsNotNone(second)
        self.assertEqual(JWT.decode(second["access_token"])["user_id"], 5)
        # Re-using the first refresh token = theft: the whole family is revoked.
        self.assertIsNone(JWT.refresh(pair["refresh_token"]))
        self.assertIsNone(JWT.refresh(second["refresh_token"]))
        third = JWT.issue_pair({"user_id": 6})
        self.assertTrue(JWT.revoke(third["refresh_token"]))
        self.assertIsNone(JWT.refresh(third["refresh_token"]))
        self.assertIsNone(JWT.refresh(third["access_token"]))  # access token is not a refresh token

    def test_validate_token_rejects_refresh_tokens(self):
        from lila.core.auth import JWT
        from lila.core.middleware import validate_token

        router = Router()

        @router.get("/api/me")
        @validate_token
        async def me(request):
            return {"id": request.state.jwt_user_id}

        client = TestClient(App(routes=[router], debug=False, rate_limit=None))
        pair = JWT.issue_pair({"user_id": 9})
        self.assertEqual(client.get("/api/me", headers={"Authorization": f"Bearer {pair['access_token']}"}).json(), {"id": 9})
        self.assertEqual(client.get("/api/me", headers={"Authorization": f"Bearer {pair['refresh_token']}"}).status_code, 401)


class ObservabilityTests(_TmpData, unittest.TestCase):
    def setUp(self):
        self._start()
        router = Router()

        @router.get("/x")
        async def x(request):
            return {"x": 1}

        self.app = App(routes=[router], debug=False, rate_limit=None, metrics=True)

    def tearDown(self):
        self._stop()

    def test_public_health_has_no_details(self):
        with TestClient(self.app) as client:
            res = client.get("/health")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json(), {"status": "ok"})

    def test_metrics_require_loopback_or_token(self):
        with TestClient(self.app, client=("203.0.113.9", 5000)) as remote:
            self.assertEqual(remote.get("/metrics").status_code, 404)
            self.assertEqual(remote.get("/health/details").status_code, 404)
        with TestClient(self.app, client=("127.0.0.1", 5000)) as local:
            local.get("/x")
            body = local.get("/metrics").text
            self.assertIn('lila_requests_total{method="GET",status="2xx"}', body)
            self.assertIn("lila_request_duration_seconds_bucket", body)
            self.assertNotIn("/x", body)              # no path labels
            proxied = local.get("/metrics", headers={"X-Forwarded-For": "203.0.113.9"})
            self.assertEqual(proxied.status_code, 404)
        with mock.patch.dict(os.environ, {"METRICS_TOKEN": "s3cret-token"}):
            with TestClient(self.app, client=("203.0.113.9", 5000)) as remote:
                self.assertEqual(remote.get("/metrics").status_code, 401)
                ok = remote.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
                self.assertEqual(ok.status_code, 200)

    def test_otp_printed_once_and_single_use(self):
        import io
        import re
        from contextlib import redirect_stderr

        with mock.patch.dict(os.environ, {"METRICS_OTP": "true"}):
            with TestClient(self.app, client=("127.0.0.1", 5000)) as local:
                buf = io.StringIO()
                with redirect_stderr(buf):
                    first = local.get("/health/details")
                self.assertEqual(first.status_code, 401)
                self.assertTrue(first.json()["otp_required"])
                code = re.search(r"code for /health/details: (\d{6})", buf.getvalue()).group(1)
                self.assertNotIn(code, first.text)
                ok = local.get("/health/details", headers={"X-Lila-OTP": code})
                self.assertEqual(ok.status_code, 200)
                self.assertIn("process", ok.json())
                with redirect_stderr(io.StringIO()):
                    again = local.get("/health/details", headers={"X-Lila-OTP": code})
                self.assertEqual(again.status_code, 401)   # single use


class ImageAndMailTests(unittest.TestCase):
    def test_responsive_image_variants(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        from lila.core.images import responsive_image

        tmp = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            os.makedirs("public/img")
            Image.new("RGB", (1200, 600), (10, 120, 200)).save("public/img/hero.jpg")
            html = str(responsive_image("img/hero.jpg", alt="Hero <x>", widths=[480, 960, 1440], class_="w-full"))
            self.assertRegex(html, r"hero-480\.webp\?v=\d+ 480w")
            self.assertRegex(html, r"hero-1200\.webp\?v=\d+ 1200w")   # never upscaled to 1440
            self.assertNotIn("1440", html)
            self.assertIn('width="1200" height="600"', html)
            self.assertIn('alt="Hero &lt;x&gt;"', html)
            self.assertIn('class="w-full"', html)
            self.assertTrue(os.path.isfile("public/img/_r/hero-960.webp"))
            outside = str(responsive_image("../../etc/passwd"))
            self.assertNotIn("srcset", outside)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)

    def test_email_template_renders_html_text_and_subject(self):
        from lila.core import templates as tpl
        from lila.core.mailer import Mailer

        tpl.jinja_env.loader.inner = ChoiceLoader([
            DictLoader({"emails/welcome.jinja": (
                '{% extends "emails/base.jinja" %}{% set subject = "Welcome " ~ name %}'
                '{% block content %}<p>Hi {{ name }}</p><a href="https://x.test/go">Start</a>{% endblock %}'
            )}),
            tpl.jinja_env.loader.inner,
        ])
        tpl.jinja_env.cache.clear()
        subject, html_body, text_body = Mailer.render_template("welcome", {"name": "Ana <3"})
        self.assertEqual(subject, "Welcome Ana <3")
        self.assertIn("Hi Ana &lt;3", html_body)
        self.assertIn("Hi Ana <3", text_body)
        self.assertIn("Start (https://x.test/go)", text_body)


if __name__ == "__main__":
    unittest.main()
