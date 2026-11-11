import os
import shutil
import tempfile
import unittest
from unittest import mock

from sqlalchemy import Column, Integer, String, text

from lila.core.base_model import BaseModel
from lila.core.database import Database


class MigrationPlanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"LILA_DATA_DIR": os.path.join(self.tmp, "data")})
        self.env.start()
        from lila.core import system_db
        system_db.close_all()
        self.db = Database(config={"type": "sqlite", "database": os.path.join(self.tmp, "plan"), "is_async": True})
        self.db.connect()
        async with self.db.engine.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE plan_products (id INTEGER PRIMARY KEY, nme VARCHAR(50), price TEXT, legacy TEXT)"
            ))

    async def asyncTearDown(self):
        from lila.core import system_db
        system_db.close_all()
        await self.db.close_async()
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def test_plan_apply_and_history(self):
        from lila.core import migrations as mig

        class PlanProduct(BaseModel):
            __tablename__ = "plan_products"
            __renamed_columns__ = {"name": "nme"}
            _connection = self.db
            id = Column(Integer, primary_key=True)
            name = Column(String(50), index=True)
            price = Column(Integer)
            stock = Column(Integer, nullable=True)
            code = Column(String(10), nullable=False)

        ops = [op for op in await mig.plan_async(self.db) if op["table"] == "plan_products"]
        kinds = {(op["kind"], op["column"]) for op in ops}
        self.assertIn(("rename_column", "name"), kinds)
        self.assertIn(("add_column", "stock"), kinds)
        self.assertIn(("add_column_manual", "code"), kinds)
        self.assertIn(("alter_type", "price"), kinds)
        self.assertIn(("drop_column", "legacy"), kinds)
        self.assertTrue(any(op["kind"] == "create_index" for op in ops))
        self.assertFalse(any(op["kind"] == "drop_column" and op["column"] == "nme" for op in ops))

        safe = [op for op in ops if op["safe"]]
        applied = await mig.apply_async(self.db, safe)
        self.assertEqual(len(applied), len(safe))
        async with self.db.engine.connect() as conn:
            cols = [r[1] for r in (await conn.execute(text("PRAGMA table_info(plan_products)"))).fetchall()]
        self.assertIn("name", cols)
        self.assertIn("stock", cols)
        self.assertIn("legacy", cols)          # not dropped without --drop-columns
        self.assertNotIn("nme", cols)

        drop = [op for op in await mig.plan_async(self.db) if op["kind"] == "drop_column" and op["table"] == "plan_products"]
        await mig.apply_async(self.db, drop, drop_columns=True)
        async with self.db.engine.connect() as conn:
            cols = [r[1] for r in (await conn.execute(text("PRAGMA table_info(plan_products)"))).fetchall()]
        self.assertNotIn("legacy", cols)

        rows = mig.history()
        self.assertTrue(any(r["kind"] == "rename_column" for r in rows))
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "data", "lila_system.db")))


if __name__ == "__main__":
    unittest.main()
