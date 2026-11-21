import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    HAS_OTEL = True
except ImportError:  # optional extra: lila-framework[otel]
    HAS_OTEL = False

from sqlalchemy import text
from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.database import Database
from lila.core.routing import Router


@unittest.skipUnless(HAS_OTEL, "opentelemetry not installed")
class TelemetryTests(unittest.TestCase):
    exporter = None

    @classmethod
    def setUpClass(cls):
        cls.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(cls.exporter))
        trace.set_tracer_provider(provider)

    def setUp(self):
        self.exporter.clear()
        self.tmp = tempfile.mkdtemp()
        self.db = Database(config={"type": "sqlite", "database": os.path.join(self.tmp, "otel"), "is_async": True})
        self.db.connect()
        router = Router()
        db = self.db

        @router.get("/items/{id:int}")
        async def item(request, id: int):
            async with db.engine.connect() as conn:
                value = (await conn.execute(text("SELECT :v AS v"), {"v": id})).scalar()
            return {"id": value}

        self.client = TestClient(App(routes=[router], rate_limit=None, debug=False, telemetry=True))

    def tearDown(self):
        self.db.run_sync(self.db.close_async())
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_http_and_sql_spans(self):
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        res = self.client.get("/items/7", headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"})
        self.assertEqual(res.json(), {"id": 7})
        spans = {s.name: s for s in self.exporter.get_finished_spans()}
        http = spans["GET /items/{id:int}"]
        self.assertEqual(http.attributes["http.route"], "/items/{id:int}")
        self.assertEqual(http.attributes["http.response.status_code"], 200)
        self.assertEqual(format(http.context.trace_id, "032x"), trace_id)  # continues the caller's trace
        sql = spans["SELECT sqlite"]
        self.assertEqual(sql.parent.span_id, http.context.span_id)
        self.assertNotIn("7", sql.attributes["db.statement"])  # parameters are never recorded

    def test_404_name_stays_low_cardinality(self):
        self.client.get("/nope/123")
        names = [s.name for s in self.exporter.get_finished_spans()]
        self.assertIn("GET 404", names)
        self.assertFalse(any("123" in n for n in names))

    def test_task_span(self):
        from lila.core.telemetry import task_span

        with task_span("send_email", 5):
            pass
        span = [s for s in self.exporter.get_finished_spans() if s.name == "task send_email"][0]
        self.assertEqual(span.attributes["lila.task.id"], "5")


if __name__ == "__main__":
    unittest.main()
