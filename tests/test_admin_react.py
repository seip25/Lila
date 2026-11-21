import os
import shutil
import unittest
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from sqlalchemy import Boolean, Column, Integer, String
from starlette.testclient import TestClient

from lila.core.admin import admin_routes
from lila.core.app import App
from lila.core.base_model import BaseModel
from lila.core.database import Database
from lila.core.routing import Router
from lila.testing import login

REACT = {"X-Lila-React": "1", "Accept": "application/json"}


class ReactAdminTests(unittest.TestCase):
    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_db")
        self.tmp = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(self.tmp, exist_ok=True)
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)
        self.db = Database(config={"type": "sqlite", "database": "admindb", "is_async": True})
        self.db.connect()

        class Gadget(BaseModel):
            __tablename__ = f"gadgets_{uuid.uuid4().hex[:8]}"
            __private_fields__ = ("secret",)
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(50), nullable=False)
            secret = Column(String(50), nullable=True)
            enabled = Column(Boolean, nullable=False, default=False)

        self.Gadget = Gadget
        self.db.run_sync(self.db.migrate_async())
        for name in ("alpha", "beta", "gamma"):
            self.db.run_sync(Gadget.insert_async(name=name, secret="s3cret"))
        router = Router()
        admin_routes(models=[Gadget], router=router, default_route="panel", react=True)
        self.client = TestClient(App(routes=[router], debug=False, rate_limit=None), raise_server_exceptions=False)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_guests_are_sent_to_login_and_login_is_a_react_page(self):
        self.assertEqual(self.client.get("/panel/gadgets", headers=REACT).status_code, 401)
        page = self.client.get("/panel/login", headers=REACT).json()
        self.assertEqual(page["component"], "Admin/Login")
        self.assertEqual(page["props"], {"prefix": "/panel"})

    def test_model_page_props_and_paginated_api(self):
        login(self.client, {"id": 1, "username": "root"}, cookie="admin_session")
        page = self.client.get("/panel/gadgets", headers=REACT).json()
        self.assertEqual(page["component"], "Admin/Panel")
        props = page["props"]
        self.assertEqual(props["view"], "model")
        self.assertEqual(props["admin"], {"username": "root"})
        self.assertEqual(props["model"]["api"], "/panel/api/gadgets")
        self.assertNotIn("secret", props["model"]["headers"])
        self.assertEqual({f["name"]: f["input_type"] for f in props["model"]["fields"]},
                         {"name": "text", "enabled": "boolean_select"})
        data = self.client.get("/panel/api/gadgets?page=1&per_page=2&sort=name&order=desc").json()
        self.assertEqual(data["total"], 3)
        self.assertEqual([g["name"] for g in data["items"]], ["gamma", "beta"])
        self.assertNotIn("secret", data["items"][0])
        self.assertEqual(self.client.get("/panel/api/gadgets?page=1&search=s3cret").json()["total"], 0)
        self.assertEqual(self.client.get("/panel/api/gadgets?page=1&sort=secret").status_code, 422)
        self.assertEqual(len(self.client.get("/panel/api/gadgets").json()), 3)  # v2.0 list

    def test_dashboard_props(self):
        login(self.client, {"id": 1, "username": "root"}, cookie="admin_session")
        props = self.client.get("/panel", headers=REACT).json()["props"]
        self.assertEqual(props["view"], "dashboard")
        self.assertIn("process_ram_mb", props["metrics"])
        self.assertEqual(props["models"], [{"name": "Gadget", "plural": "gadgets"}])


if __name__ == "__main__":
    unittest.main()
