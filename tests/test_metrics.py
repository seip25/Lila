import unittest
from lila.core import debug


class MetricsTests(unittest.TestCase):
    def test_metrics_standard(self):
        metrics = debug.get_system_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn("process_ram_mb", metrics)
        self.assertIn("process_memory_mb", metrics)
        self.assertIn("cpu_percent", metrics)
        self.assertIn("process_cpu", metrics)
        self.assertIn("system_ram_percent", metrics)
        self.assertIn("system_used_mb", metrics)
        self.assertIn("system_total_mb", metrics)
        self.assertIn("threads", metrics)

        self.assertGreater(metrics["process_ram_mb"], 0)
        self.assertEqual(metrics["process_ram_mb"], metrics["process_memory_mb"])
        self.assertGreaterEqual(metrics["threads"], 1)
        self.assertGreater(metrics["system_total_mb"], 0)

    def test_metrics_fallback_without_psutil(self):
        # Save original state
        orig_has = debug.HAS_PSUTIL
        orig_proc = debug._PSUTIL_PROC
        orig_cache = debug._LAST_METRICS
        orig_ts = debug._LAST_METRICS_TIME

        try:
            # Force fallback mode
            debug.HAS_PSUTIL = False
            debug._PSUTIL_PROC = None
            debug._LAST_METRICS = None
            debug._LAST_METRICS_TIME = 0.0

            metrics = debug.get_system_metrics()
            self.assertIsInstance(metrics, dict)
            self.assertFalse(metrics["psutil_available"])
            self.assertGreater(metrics["process_ram_mb"], 0)
            self.assertEqual(metrics["process_ram_mb"], metrics["process_memory_mb"])
            self.assertGreaterEqual(metrics["threads"], 1)
            self.assertGreater(metrics["system_total_mb"], 0)
            self.assertGreaterEqual(metrics["system_ram_percent"], 0)
        finally:
            debug.HAS_PSUTIL = orig_has
            debug._PSUTIL_PROC = orig_proc
            debug._LAST_METRICS = orig_cache
            debug._LAST_METRICS_TIME = orig_ts


if __name__ == "__main__":
    unittest.main()
