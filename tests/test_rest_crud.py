import os
import shutil
import unittest
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from sqlalchemy import Column, Integer, String
from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.base_model import BaseModel
from lila.core.database import Database
from lila.core.routing import Router


class RestCrudTests(unittest.TestCase):
    def setUp(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_db")
        self.tmp = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(self.tmp, exist_ok=True)
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)
        self.db = Database(config={"type": "sqlite", "database": "restdb", "is_async": True})
        self.db.connect()

        class Note(BaseModel):
            __tablename__ = f"notes_{uuid.uuid4().hex[:8]}"
            __private_fields__ = ("secret",)
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            title = Column(String(50), nullable=False)
            secret = Column(String(50), nullable=True)
            active = Column(Integer, nullable=False, default=1)

        self.Note = Note
        self.db.run_sync(self.db.migrate_async())
        router = Router(prefix="/api")
        router.rest_crud_generate(Note, base_route="notes", max_limit=10)
        app = App(routes=[router], debug=False, rate_limit=None)
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.db.run_sync(self.db.close_async())
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_and_read(self):
        res = self.client.post("/api/notes", json={"title": "hi"})
        self.assertEqual(res.status_code, 201, res.text)
        note_id = res.json()["data"]["id"]
        self.assertEqual(self.client.get(f"/api/notes/{note_id}").json()["title"], "hi")

    def test_rejects_primary_key_private_and_unknown_fields(self):
        for body in ({"title": "x", "id": 99}, {"title": "x", "secret": "s"}, {"title": "x", "nope": 1}):
            res = self.client.post("/api/notes", json=body)
            self.assertEqual(res.status_code, 422, body)

    def test_db_errors_are_not_leaked(self):
        res = self.client.post("/api/notes", json={})  # title is NOT NULL
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("NOT NULL", res.text)
        self.assertNotIn("sqlite", res.text.lower())


if __name__ == "__main__":
    unittest.main()
