import os
import shutil
import uuid
import unittest

from sqlalchemy import Column, Integer, String

from lila.core.database import Database
from lila.core.base_model import BaseModel


def _tmpdir() -> str:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_db")
    path = os.path.join(root, uuid.uuid4().hex)
    os.makedirs(path, exist_ok=True)
    return path


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = _tmpdir()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)
        self.db = Database(config={"type": "sqlite", "database": "testdb", "is_async": True})
        self.db.connect()

    async def asyncTearDown(self):
        await self.db.close_async()
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def test_crud_and_partial_select(self):
        class Widget(BaseModel):
            __tablename__ = "widgets_test"
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(50), nullable=False)
            active = Column(Integer, nullable=False, default=1)

        await self.db.migrate_async()
        created = await Widget.insert_async(name="alpha")
        self.assertEqual(created["name"], "alpha")
        partial = await Widget.get_by_id_async(created["id"], select="id,name")
        self.assertEqual(partial, {"id": created["id"], "name": "alpha"})
        self.assertTrue(await Widget.update_async(created["id"], name="beta"))
        self.assertEqual(await Widget.count_async(), 1)
        self.assertTrue(await Widget.delete_async(created["id"]))
        self.assertEqual(await Widget.get_all_async(), [])

    async def test_migrate_adds_missing_column(self):
        class Widget2(BaseModel):
            __tablename__ = "widgets_cols"
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(50), nullable=False)
            active = Column(Integer, nullable=False, default=1)

        await self.db.migrate_async()
        Widget2.__table__.append_column(Column("price", Integer, nullable=True))
        report = await self.db.migrate_async()
        self.assertIn("widgets_cols.price", report["added_columns"])

    async def test_query_async_insert_without_rows_does_not_raise(self):
        await self.db.query_async("CREATE TABLE raw_table (id INTEGER PRIMARY KEY, name TEXT)")
        result = await self.db.query_async("INSERT INTO raw_table(name) VALUES ('x')", return_rows=True)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
