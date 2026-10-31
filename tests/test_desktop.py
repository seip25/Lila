import unittest
import uuid
from lila.cli.desktop import DesktopBridge, acquire_single_instance_lock


class DesktopTests(unittest.TestCase):
    def test_single_instance_lock(self):
        unique_name = f"TestApp_{uuid.uuid4().hex}"
        # First lock acquisition should succeed
        lock1 = acquire_single_instance_lock(unique_name)
        self.assertIsNotNone(lock1, "First instance lock should be acquired")

        # Second lock acquisition for the same app name should fail (single instance)
        lock2 = acquire_single_instance_lock(unique_name)
        self.assertIsNone(lock2, "Second instance lock must return None to prevent duplicate windows")

    def test_desktop_bridge_methods(self):
        bridge = DesktopBridge()
        # Test get_system_metrics
        metrics = bridge.get_system_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn("process_ram_mb", metrics)
        self.assertIn("cpu_percent", metrics)
        self.assertGreater(metrics["process_ram_mb"], 0)

        # File dialogs return None when run in headless testing without webview window
        self.assertIsNone(bridge.open_file_dialog())
        self.assertIsNone(bridge.save_file_dialog())
        self.assertIsNone(bridge.select_folder_dialog())

    def test_desktop_build_paths_includes_lila(self):
        import os
        import lila
        lila_pkg_dir = os.path.dirname(os.path.abspath(lila.__file__))
        lila_root = os.path.dirname(lila_pkg_dir)
        self.assertTrue(os.path.isdir(lila_pkg_dir))
        self.assertTrue(os.path.isdir(lila_root))
        self.assertTrue(os.path.isfile(os.path.join(lila_pkg_dir, "core", "app.py")))


if __name__ == "__main__":
    unittest.main()
