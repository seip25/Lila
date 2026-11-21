import os
import shutil
import tempfile
import unittest
from unittest import mock

from sqlalchemy import Column, Index, Integer, MetaData, String, Table, inspect as sa_inspect

from lila.core.database import Database


def v1(md):
    return Table("rb_items", md, Column("id", Integer, primary_key=True), Column("name", String(50)))


def v2(md):
    return Table(
        "rb_items", md,
        Column("id", Integer, primary_key=True),
        Column("full_name", String(50), info={"renamed_from": "name"}),
        Column("age", Integer, nullable=True),
        Index("ix_rb_items_age", "age"),
    )


class MigrationRollbackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"LILA_DATA_DIR": os.path.join(self.tmp, "data")})
        self.env.start()
        from lila.core import system_db

        system_db.close_all()
        self.db = Database(config={"type": "sqlite", "database": os.path.join(self.tmp, "rb"), "is_async": True})
        self.db.connect()

    async def asyncTearDown(self):
        from lila.core import system_db

        system_db.close_all()
        await self.db.close_async()
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def _schema(self):
        async with self.db.engine.connect() as conn:
            def read(sc):
                insp = sa_inspect(sc)
                if "rb_items" not in insp.get_table_names():
                    return None
                return ({c["name"] for c in insp.get_columns("rb_items")}, {i["name"] for i in insp.get_indexes("rb_items")})
            return await conn.run_sync(read)

    async def _migrate(self, md):
        from lila.core import migrations as mig

        ops = [op for op in await mig.plan_async(self.db, metadata=md) if op["safe"]]
        return await mig.apply_async(self.db, ops, metadata=md)

    async def test_rollback_batches(self):
        from lila.core import migrations as mig

        md1 = MetaData(); v1(md1)
        await self._migrate(md1)
        md2 = MetaData(); v2(md2)
        applied = await self._migrate(md2)
        self.assertEqual({op["kind"] for op in applied}, {"rename_column", "add_column", "create_index"})
        self.assertEqual(await self._schema(), ({"id", "full_name", "age"}, {"ix_rb_items_age"}))

        key = mig.database_key(self.db)
        plan = mig.rollback_plan(key, steps=1)
        self.assertEqual({op["batch"] for op in plan}, {2})
        self.assertEqual({op["kind"]: op["destructive"] for op in plan},
                         {"create_index": False, "add_column": True, "rename_column": False})

        # Without permission only the safe steps run.
        undone = await mig.rollback_async(self.db, plan)
        self.assertEqual({op["kind"] for op in undone}, {"create_index", "rename_column"})
        self.assertEqual(await self._schema(), ({"id", "name", "age"}, set()))

        # The destructive step stays pending in the same batch.
        plan = mig.rollback_plan(key, steps=1)
        self.assertEqual([op["kind"] for op in plan], ["add_column"])
        await mig.rollback_async(self.db, plan, allow_destructive=True)
        self.assertEqual(await self._schema(), ({"id", "name"}, set()))

        plan = mig.rollback_plan(key, steps=1)
        self.assertEqual([(op["batch"], op["kind"]) for op in plan], [(1, "create_table")])
        await mig.rollback_async(self.db, plan, allow_destructive=True)
        self.assertIsNone(await self._schema())
        self.assertEqual(mig.rollback_plan(key), [])
        kinds = [row["kind"] for row in mig.history(20)]
        self.assertIn("rollback:create_table", kinds)


if __name__ == "__main__":
    unittest.main()
