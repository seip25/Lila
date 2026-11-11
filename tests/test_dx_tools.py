import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from sqlalchemy import Column, Integer, String

from lila.core.app import App
from lila.core.base_model import BaseModel
from lila.core.config import ENV_CONFIG, validate_settings
from lila.core.routing import Router
from lila.testing import TestClient, csrf_headers, login, override_env, temp_database


router = Router(prefix="/api")


@router.get("/me", auth=True)
async def me(request):
    return {"user": request.state.user}


@router.post("/save", csrf=True)
async def save(request):
    return {"ok": True}


class TestingHelpersTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(App(routes=[router], debug=False, rate_limit=None))

    def test_login_and_csrf_helpers(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        login(self.client, {"id": 7, "email": "a@b.c", "password": "never-stored"})
        data = self.client.get("/api/me").json()["user"]
        self.assertEqual(data["id"], 7)
        self.assertNotIn("password", data)
        self.assertEqual(self.client.post("/api/save").status_code, 403)
        self.assertEqual(self.client.post("/api/save", headers=csrf_headers(self.client)).status_code, 200)

    def test_override_env(self):
        with override_env(CACHE_MAX_MB="12", LILA_TEST_FLAG="1"):
            self.assertEqual(os.environ["LILA_TEST_FLAG"], "1")
        self.assertNotIn("LILA_TEST_FLAG", os.environ)


class TempDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_temp_database(self):
        class Note(BaseModel):
            __tablename__ = "notes_tmpdb"
            id = Column(Integer, primary_key=True, autoincrement=True)
            title = Column(String(20))
            active = Column(Integer, default=1)

        async with temp_database(Note) as db:
            await Note.insert_async(title="hi")
            self.assertEqual(await Note.count_async(), 1)
            self.assertIs(Note._connection, db)
        self.assertIsNone(Note.__dict__.get("_connection"))


class SettingsValidationTests(unittest.TestCase):
    def test_errors_and_warnings(self):
        errors, warnings = validate_settings({"PORT": "abc", "CACHE_DRIVER": "mem", "APP_URL": "example.com",
                                              "DEBUG": "True", "APP_ENV": "production"})
        joined = " ".join(errors)
        self.assertIn("PORT", joined)
        self.assertIn("CACHE_DRIVER", joined)
        self.assertIn("APP_URL", joined)
        self.assertTrue(any("DEBUG=True" in w for w in warnings))
        self.assertEqual(validate_settings({"PORT": "8000", "APP_URL": "https://x.com"}), ([], []))


class I18nCheckTests(unittest.TestCase):
    def test_reports_missing_keys_per_language(self):
        from lila.core.i18n_check import check

        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, "resources", "html"))
            os.makedirs(os.path.join(tmp, "app", "locales"))
            with open(os.path.join(tmp, "resources", "html", "p.jinja"), "w") as fh:
                fh.write("{{ translate['only_in_es'] }} {{ t('everywhere') }}")
            with open(os.path.join(tmp, "app", "locales", "es.json"), "w") as fh:
                fh.write('{"only_in_es": "x", "everywhere": "y"}')
            with open(os.path.join(tmp, "app", "locales", "en.json"), "w") as fh:
                fh.write('{"everywhere": "y"}')
            report = check(tmp)
            self.assertIn("only_in_es", report["missing"]["en"])
            self.assertNotIn("es", report["missing"])
            self.assertIn("only_in_es", report["parity"]["en"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
