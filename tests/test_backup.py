import os
import sqlite3
import tempfile
import time
import unittest

from lila.cli.backup import run_sqlite_backup


class BackupTests(unittest.TestCase):
    def test_sqlite_hot_backup(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            src_db = os.path.join(tmp_dir, "test_app.sqlite")
            backup_dir = os.path.join(tmp_dir, "backups")

            # Create source database with table and rows in WAL mode
            conn = sqlite3.connect(src_db)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
                conn.execute("INSERT INTO users (name) VALUES ('Alice'), ('Bob');")
                conn.commit()
            finally:
                conn.close()

            # Execute hot backup
            info = run_sqlite_backup(
                source_db_path=src_db,
                output_path=backup_dir,
                max_backups=2,
            )

            dst_path = info["destination"]
            self.assertTrue(os.path.isfile(dst_path), "Backup file must exist on disk")
            self.assertGreater(info["size_bytes"], 0)
            self.assertGreater(info["duration_ms"], 0)

            # Verify integrity of backup by querying it
            bkp_conn = sqlite3.connect(dst_path)
            try:
                cursor = bkp_conn.cursor()
                cursor.execute("SELECT name FROM users ORDER BY id;")
                rows = cursor.fetchall()
                self.assertEqual(rows, [("Alice",), ("Bob",)])
            finally:
                bkp_conn.close()

            # Test rotation: create 2 more backups to trigger pruning (max_backups=2)
            time.sleep(0.02)
            run_sqlite_backup(source_db_path=src_db, output_path=backup_dir, max_backups=2)
            time.sleep(0.02)
            info3 = run_sqlite_backup(source_db_path=src_db, output_path=backup_dir, max_backups=2)
            self.assertGreaterEqual(info3["rotated"], 1, "Should have rotated older backups")

            remaining_files = [f for f in os.listdir(backup_dir) if f.endswith(".sqlite")]
            self.assertLessEqual(len(remaining_files), 2, "Should keep at most max_backups")


if __name__ == "__main__":
    unittest.main()
