import os
import shutil
import uuid
import unittest
from datetime import datetime, date
from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, Date

from lila.core.database import Database
from lila.core.base_model import BaseModel
from lila.core.admin import _coerce_payload_for_model
from lila.core.auth import PasswordHasher


def _tmpdir() -> str:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_admin_db")
    path = os.path.join(root, uuid.uuid4().hex)
    os.makedirs(path, exist_ok=True)
    return path


class AdminCrudTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = _tmpdir()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)
        self.db = Database(config={"type": "sqlite", "database": "admindb", "is_async": True})
        self.db.connect()

    async def asyncTearDown(self):
        await self.db.close_async()
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_coerce_payload_types(self):
        class DummyUser(BaseModel):
            __tablename__ = "dummy_users_coerce"
            id = Column(Integer, primary_key=True)
            age = Column(Integer)
            score = Column(Float)
            is_active = Column(Boolean)
            created_at = Column(DateTime)
            birth_date = Column(Date)
            bio = Column(String(100), nullable=True)
            password = Column(String(255))

        # Test FormData string inputs on create
        payload = {
            "id": "99",  # should be ignored
            "age": "25",
            "score": "98.5",
            "is_active": "true",
            "birth_date": "1995-05-12",
            "bio": "",
            "password": "secret_password_123",
        }

        coerced = _coerce_payload_for_model(DummyUser, payload, is_update=False)

        self.assertNotIn("id", coerced)
        self.assertEqual(coerced["age"], 25)
        self.assertEqual(coerced["score"], 98.5)
        self.assertIs(coerced["is_active"], True)
        self.assertEqual(coerced["birth_date"], date(1995, 5, 12))
        self.assertIsNone(coerced["bio"])
        # Password must be hashed
        self.assertTrue(PasswordHasher.verify(coerced["password"], "secret_password_123"))

    def test_coerce_password_empty_on_update_is_omitted(self):
        class DummyUser2(BaseModel):
            __tablename__ = "dummy_users_update"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            password = Column(String(255))

        # When updating and password is empty, key must be dropped so hash is preserved
        payload = {
            "name": "Updated Name",
            "password": "",
        }

        coerced = _coerce_payload_for_model(DummyUser2, payload, is_update=True)
        self.assertEqual(coerced["name"], "Updated Name")
        self.assertNotIn("password", coerced)

    def test_coerce_default_column_omitted_on_create_when_empty(self):
        class Item(BaseModel):
            __tablename__ = "items_default"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))
            status = Column(String(20), default="pending")
            notes = Column(String(100), nullable=True)

        payload = {
            "name": "Widget",
            "status": "",
            "notes": "",
        }

        coerced = _coerce_payload_for_model(Item, payload, is_update=False)
        self.assertEqual(coerced["name"], "Widget")
        self.assertNotIn("status", coerced)  # Has default, so omitted to let default apply
        self.assertIsNone(coerced["notes"])  # Nullable, converted to None

    async def test_admin_crud_workflow_with_coercion(self):
        class Member(BaseModel):
            __tablename__ = "members_table"
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            username = Column(String(50), nullable=False)
            level = Column(Integer, default=1)
            active = Column(Boolean, default=True)
            password = Column(String(255), nullable=False)

        await self.db.migrate_async()

        # Simulate create with FormData string values
        create_data = {
            "username": "alice",
            "level": "5",
            "active": "1",
            "password": "super_secret_pw",
        }
        coerced_create = _coerce_payload_for_model(Member, create_data, is_update=False)
        created = await Member.insert_async(**coerced_create)
        self.assertIsNotNone(created["id"])
        self.assertEqual(created["username"], "alice")
        self.assertEqual(created["level"], 5)
        self.assertTrue(PasswordHasher.verify(created["password"], "super_secret_pw"))

        original_hash = created["password"]

        # Simulate update with empty password string
        update_data = {
            "username": "alice_renamed",
            "level": "6",
            "password": "",
        }
        coerced_update = _coerce_payload_for_model(Member, update_data, is_update=True)
        self.assertNotIn("password", coerced_update)

        await Member.update_async(created["id"], **coerced_update)
        updated = await Member.get_by_id_async(created["id"])
        self.assertEqual(updated["username"], "alice_renamed")
        self.assertEqual(updated["level"], 6)
        self.assertEqual(updated["password"], original_hash)


if __name__ == "__main__":
    unittest.main()
