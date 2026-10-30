import os
import shutil
import uuid
import unittest

from lila.core.cache import Cache


class CacheTests(unittest.TestCase):
    def setUp(self):
        Cache.configure("memory")

    def test_memory_basic_and_incr(self):
        Cache.set("k", {"a": 1}, ttl=30)
        self.assertEqual(Cache.get("k"), {"a": 1})
        self.assertEqual(Cache.incr("counter", ttl=30), 1)
        self.assertEqual(Cache.incr("counter", ttl=30), 2)
        Cache.delete("k")
        self.assertIsNone(Cache.get("k"))

    def test_clear_preserves_sessions(self):
        Cache.set("session:abc", {"user_id": 1}, ttl=30)
        Cache.set("route:abc", {"x": 1}, ttl=30)
        Cache.clear(include_sessions=False)
        self.assertIsNone(Cache.get("route:abc"))
        self.assertEqual(Cache.get("session:abc"), {"user_id": 1})
        Cache.clear(include_sessions=True)
        self.assertIsNone(Cache.get("session:abc"))

    def test_file_driver(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_cache")
        work = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(work, exist_ok=True)
        try:
            Cache.configure("file", {"dir": work})
            Cache.set("f", {"v": 1}, ttl=30)
            self.assertEqual(Cache.get("f"), {"v": 1})
            Cache.set("session:abc", {"user_id": 1}, ttl=30)
            Cache.clear(include_sessions=False)
            self.assertIsNone(Cache.get("f"))
            self.assertEqual(Cache.get("session:abc"), {"user_id": 1})
            Cache.delete("f")
            self.assertIsNone(Cache.get("f"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
            Cache.configure("memory")


if __name__ == "__main__":
    unittest.main()
