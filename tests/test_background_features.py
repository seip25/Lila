import asyncio
import datetime as dt
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from lila.core import system_db


class _DataDirMixin:
    def _setup_data_dir(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"LILA_DATA_DIR": self.tmp})
        self.env.start()
        system_db.close_all()

    def _teardown_data_dir(self):
        system_db.close_all()
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


CALLS = []


class TaskQueueTests(_DataDirMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._setup_data_dir()
        CALLS.clear()

    async def asyncTearDown(self):
        from lila.core import tasks
        await tasks.stop_consumers()
        self._teardown_data_dir()

    async def test_delay_run_retry_and_dead(self):
        from lila.core import tasks

        @tasks.task(name="test:add", retries=2, backoff=0.01)
        async def add(a, b):
            CALLS.append(a + b)

        @tasks.task(name="test:boom", retries=2, backoff=0.01)
        def boom():
            raise RuntimeError("nope")

        task_id = await add.delay(2, 3)
        self.assertGreater(task_id, 0)
        self.assertEqual(await tasks.run_one(), "done")
        self.assertEqual(CALLS, [5])
        self.assertIsNone(await tasks.run_one())          # queue empty

        await boom.delay()
        self.assertEqual(await tasks.run_one(), "retry")
        await asyncio.sleep(0.05)
        self.assertEqual(await tasks.run_one(), "dead")
        self.assertEqual(tasks.stats().get("dead"), 1)
        dead = tasks.list_tasks("dead")[0]
        self.assertIn("RuntimeError", dead["last_error"])
        later = await add.delay(1, 1, _in=60)
        self.assertIsNone(await tasks.run_one())          # not due yet
        self.assertTrue(any(t["id"] == later for t in tasks.list_tasks("queued")))

        self.assertTrue(tasks.retry(dead["id"]))
        self.assertEqual(tasks.stats().get("queued"), 2)

    async def test_consumers_process_in_background(self):
        from lila.core import tasks

        @tasks.task(name="test:bg")
        async def bg(x):
            CALLS.append(x)

        await tasks.start_consumers(2)
        for i in range(5):
            await bg.delay(i)
        for _ in range(50):
            if len(CALLS) == 5:
                break
            await asyncio.sleep(0.05)
        self.assertEqual(sorted(CALLS), [0, 1, 2, 3, 4])

    async def test_unregistered_module_is_rejected(self):
        from lila.core import tasks

        await tasks.enqueue("os:system", args=["echo hacked"], retries=1)
        self.assertEqual(await tasks.run_one(), "dead")
        self.assertIn("LILA_TASK_MODULES", tasks.list_tasks("dead")[0]["last_error"])


class SchedulerTests(_DataDirMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._setup_data_dir()

    async def asyncTearDown(self):
        from lila.core import scheduler
        await scheduler.stop()
        scheduler._JOBS.clear()
        self._teardown_data_dir()

    def test_cron_expressions(self):
        from lila.core.scheduler import CronSchedule

        sat = dt.datetime(2026, 11, 14, 20, 0)
        self.assertEqual(CronSchedule("*/15 9-18 * * mon-fri").next_after(sat), dt.datetime(2026, 11, 16, 9, 0))
        self.assertEqual(CronSchedule("0 3 * * *").next_after(dt.datetime(2026, 11, 11, 3, 0)), dt.datetime(2026, 11, 12, 3, 0))
        self.assertEqual(CronSchedule("0 0 * * 5-7").next_after(dt.datetime(2026, 11, 11)), dt.datetime(2026, 11, 13))
        with self.assertRaises(ValueError):
            CronSchedule("61 * * * *")

    async def test_every_job_runs_once_per_interval_and_records(self):
        from lila.core import scheduler

        runs = []

        @scheduler.every(seconds=1, run_on_start=True, name="test:tick")
        def tick():
            runs.append(time.time())

        await scheduler.start()
        await asyncio.sleep(1.6)
        await scheduler.stop()
        self.assertGreaterEqual(len(runs), 2)
        self.assertLessEqual(len(runs), 3)
        self.assertEqual(scheduler.last_runs()["test:tick"]["last_status"], "ok")

    async def test_only_one_leader(self):
        from lila.core.scheduler import _LeaderLock

        path = os.path.join(self.tmp, "x.lock")
        first, second = _LeaderLock(path), _LeaderLock(path)
        self.assertTrue(first.acquire())
        if os.name != "nt":
            # flock is per open file description: a second handle in the same
            # process is rejected exactly like another worker process would be.
            self.assertFalse(second.acquire())
        first.release()
        self.assertTrue(second.acquire())
        second.release()


class SSETests(unittest.TestCase):
    def test_format_event(self):
        from lila.core.sse import format_event

        out = format_event({"a": 1}, event="notice", id="7")
        self.assertEqual(out, b'event: notice\nid: 7\ndata: {"a":1}\n\n')
        self.assertEqual(format_event("two\nlines"), b"data: two\ndata: lines\n\n")

    def test_event_stream_and_channel(self):
        from starlette.testclient import TestClient

        from lila.core.app import App
        from lila.core.routing import Router
        from lila.core.sse import Channel, EventStream

        router = Router()
        channel = Channel("test-sse")

        @router.get("/progress")
        async def progress(request):
            async def steps():
                for pct in (0, 50, 100):
                    yield {"event": "progress", "data": {"pct": pct}}
            return EventStream(request, steps())

        client = TestClient(App(routes=[router], debug=False, rate_limit=None))
        with client.stream("GET", "/progress") as res:
            self.assertEqual(res.headers["content-type"].split(";")[0], "text/event-stream")
            self.assertIsNone(res.headers.get("content-encoding"))
            body = b"".join(res.iter_bytes())
        self.assertIn(b"event: ready", body)
        self.assertIn(b'event: progress\ndata: {"pct":100}', body)

        async def publish_flow():
            got = []
            queue = asyncio.Queue()
            entry = (queue, "user:7")
            channel._subscribers.add(entry)
            channel._subscribers.add((asyncio.Queue(), "user:8"))
            self.assertEqual(await channel.publish({"m": 1}, event="n", to="user:7"), 1)
            self.assertEqual(await channel.publish({"m": 2}, event="n"), 2)
            got.append(queue.get_nowait())
            got.append(queue.get_nowait())
            channel._subscribers.clear()
            return got

        got = asyncio.run(publish_flow())
        self.assertEqual([g["data"]["m"] for g in got], [1, 2])


if __name__ == "__main__":
    unittest.main()
