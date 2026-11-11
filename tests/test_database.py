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

    async def test_filters_order_and_cache_isolation(self):
        class Gadget(BaseModel):
            __tablename__ = "gadgets_test"
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(50), nullable=False)
            active = Column(Integer, nullable=False, default=1)

        await self.db.migrate_async()
        await Gadget.insert_async(name="b")
        await Gadget.insert_async(name="a")
        rows = await Gadget.get_all_async(order_by="name")
        self.assertEqual([r["name"] for r in rows], ["a", "b"])
        # Mutating a result must not leak into the shared read cache.
        rows[0]["name"] = "mutated"
        again = await Gadget.get_all_async(order_by="name")
        self.assertEqual(again[0]["name"], "a")
        # Unknown filters / methods are rejected instead of returning all rows.
        with self.assertRaises(ValueError):
            await Gadget.get_all_async(nmae="a")
        with self.assertRaises(ValueError):
            await Gadget.get_all_async(to_dict="a")
        self.assertEqual(await Gadget.count_async(name="a"), 1)

        # Soft-deleted rows are not updated unless restored explicitly.
        target = rows[1]["id"]
        self.assertTrue(await Gadget.delete_async(target))
        self.assertFalse(await Gadget.update_async(target, name="ghost"))
        self.assertTrue(await Gadget.update_async(target, active=1))
        self.assertEqual((await Gadget.get_by_id_async(target))["name"], "b")

    async def test_rich_filters_pagination_and_private_fields(self):
        class Item(BaseModel):
            __tablename__ = "items_rich"
            __private_fields__ = ("secret",)
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(50), nullable=False)
            price = Column(Integer, nullable=False, default=0)
            secret = Column(String(50), nullable=True)
            active = Column(Integer, nullable=False, default=1)

        await self.db.migrate_async()
        for i in range(1, 26):
            await Item.insert_async(name=f"item-{i:02d}", price=i, secret="s")
        rows = await Item.get_all_async(price__gte=20, order_by="price", desc=True)
        self.assertEqual([r["price"] for r in rows], [25, 24, 23, 22, 21, 20])
        self.assertNotIn("secret", rows[0])                     # never selected
        self.assertEqual(len(await Item.get_all_async(id__in=[1, 2, 3])), 3)
        self.assertEqual(len(await Item.get_all_async(name__contains="-1")), 10)
        self.assertEqual(await Item.count_async(price__lt=5), 4)
        with self.assertRaises(ValueError):
            await Item.get_all_async(price__between=3)
        with self.assertRaises(ValueError):
            await Item.get_all_async(order_by="nope")
        page = await Item.paginate_async(page=3, per_page=10, order_by="price")
        self.assertEqual(page["total"], 25)
        self.assertEqual(page["pages"], 3)
        self.assertEqual([r["price"] for r in page["items"]], [21, 22, 23, 24, 25])
        self.assertFalse(page["has_next"])
        self.assertEqual(page["prev_page"], 2)
        clamped = await Item.paginate_async(page=99, per_page=1000)
        self.assertEqual(clamped["per_page"], 100)
        self.assertEqual(clamped["page"], 1)
        one = await Item.get_by_id_async(1)
        self.assertEqual(one["name"], "item-01")
        self.assertNotIn("secret", one)

    async def test_concurrent_writes_are_serialized_on_sqlite(self):
        import asyncio

        class Log(BaseModel):
            __tablename__ = "logs_concurrent"
            _connection = self.db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(50), nullable=False)
            active = Column(Integer, nullable=False, default=1)

        await self.db.migrate_async()
        await asyncio.gather(*(Log.insert_async(name=f"n{i}") for i in range(60)))
        self.assertEqual(await Log.count_async(), 60)

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
