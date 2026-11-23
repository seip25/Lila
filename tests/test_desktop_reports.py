import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from sqlalchemy import Column, Integer, String
from starlette.testclient import TestClient

from lila.cli.desktop import DesktopBridge
from lila.cli.scaffold import copy_item
from lila.core import desktop as desktop_mod
from lila.core import desktop_menu, desktop_reports
from lila.core.app import App
from lila.core.base_model import BaseModel
from lila.core.cache import Cache
from lila.core.database import Database
from lila.core.migrations import auto_migrate_async
from lila.core.routing import Router


class _FakeWindow:
    def __init__(self):
        self.scripts = []

    def evaluate_js(self, script: str):
        self.scripts.append(script)
        return False


class _FakeMenu:
    def __init__(self, title, items=None):
        self.title = title
        self.items = list(items or [])


class _FakeMenuAction:
    def __init__(self, title, function):
        self.title = title
        self.function = function


class _FakeMenuSeparator:
    pass


class DesktopReportsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lila_reports_")
        self.db_path = os.path.join(self.tmp, "app", "desktop", "database", "reports.db")
        self._saved_env = {
            k: os.environ.get(k)
            for k in (
                "DESKTOP_REPORT_URL",
                "DESKTOP_REPORT_TOKEN",
                "LILA_DESKTOP_REPORTS_DB",
                "LILA_LOG_DIR",
            )
        }
        Cache.clear()

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disabled_by_default(self):
        app = App(routes=[], debug=False, rate_limit=None)
        client = TestClient(app, raise_server_exceptions=False)
        self.assertEqual(client.post("/api/desktop/bug", json={}).status_code, 404)
        self.assertEqual(client.post("/api/desktop/telemetry", json={}).status_code, 404)

    def test_ingest_dedup_security_pii_and_pruning(self):
        app = App(
            routes=[],
            debug=False,
            rate_limit=None,
            desktop_reports={
                "db_path": self.db_path,
                "token": "secret-report-token",
                "max_body_bytes": 4096,
                "rate_limit": (5, 60),
                "retention_days": 90,
            },
        )

        # All desktop_reports routes are web-only (desktop=False)
        desktop_kept, desktop_removed = desktop_mod.filter_routes(app.routes, desktop=True)
        removed_paths = {getattr(r, "path", "") for r in desktop_removed}
        self.assertIn("/api/desktop/bug", removed_paths)
        self.assertIn("/api/desktop/telemetry", removed_paths)
        self.assertIn("/api/desktop/reports", removed_paths)
        self.assertNotIn("/api/desktop/bug", {getattr(r, "path", "") for r in desktop_kept})

        client = TestClient(app, raise_server_exceptions=False)

        # Unauthenticated GET /reports and missing token POST /bug are 401
        self.assertEqual(client.get("/api/desktop/reports").status_code, 401)
        self.assertEqual(client.get("/api/desktop/reports/stats").status_code, 401)
        self.assertEqual(client.post("/api/desktop/bug", json={}).status_code, 401)

        headers = {"X-Lila-Report-Token": "secret-report-token"}

        # Seed an old (> 90 days) report to verify background retention pruning on upload
        conn = desktop_reports._connect_db(self.db_path)
        try:
            old_ts = time.time() - (95 * 86400)
            conn.execute(
                """
                INSERT INTO desktop_reports (
                    kind, app_name, app_version, lila_version, platform, os_version,
                    install_id, period_key, content_hash, log_date, log_type,
                    user_note, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "telemetry",
                    "TestApp",
                    "1.0.0",
                    "2.2.2",
                    "windows",
                    "Windows 11",
                    "install_old_1234",
                    "2025-01-01",
                    "0" * 64,
                    "2025-01-01",
                    "error",
                    "",
                    "{}",
                    old_ts,
                ),
            )
        finally:
            conn.close()

        # Oversized body -> 413
        oversized = {"install_id": "inst_12345678", "period_key": "2026-11-23", "logs": "x" * 5000}
        self.assertEqual(client.post("/api/desktop/bug", json=oversized, headers=headers).status_code, 413)

        # Valid bug report with PII -> 201 stored, PII redacted
        payload = {
            "app_name": "TodoDesktop",
            "app_version": "1.2.0",
            "lila_version": "2.2.2",
            "platform": "windows",
            "os_version": "Windows 11",
            "install_id": "inst_12345678",
            "period_key": "2026-11-23",
            "log_date": "2026-11-23",
            "log_type": "error",
            "user_note": r"Crash for alice@example.com in C:\Users\Alice\AppData\Local\Todo",
            "logs": "Authorization: Bearer super_secret_token_9999\napi_key=sk_live_12345",
        }
        r1 = client.post("/api/desktop/bug", json=payload, headers=headers)
        self.assertEqual(r1.status_code, 201, r1.text)
        self.assertTrue(r1.json()["stored"])

        # Duplicate report -> 200 duplicate (same version + install_id + period_key + hash)
        r2 = client.post("/api/desktop/bug", json=payload, headers=headers)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertFalse(r2.json()["stored"])
        self.assertEqual(r2.json()["status"], "duplicate")

        # Rate limit (5/60s): 401 (#1), 413 (#2), r1 (#3), r2 (#4), r3 (#5) pass; r4 (#6) -> 429
        r3 = client.post("/api/desktop/bug", json={**payload, "user_note": "another"}, headers=headers)
        self.assertEqual(r3.status_code, 201)
        r4 = client.post("/api/desktop/bug", json={**payload, "user_note": "sixth"}, headers=headers)
        self.assertEqual(r4.status_code, 429)

        # Verify old 95-day row was pruned by BackgroundTask and PII was redacted
        listing = client.get("/api/desktop/reports", headers=headers)
        self.assertEqual(listing.status_code, 200)
        items = listing.json()["items"]
        self.assertEqual(len(items), 2)
        notes = " ".join(i["user_note"] for i in items)
        logs = " ".join(i["payload"]["logs"] for i in items)
        self.assertNotIn("alice@example.com", notes)
        self.assertNotIn("Alice", notes)
        self.assertIn("[email]", notes)
        self.assertIn("[user]", notes)
        self.assertNotIn("super_secret_token_9999", logs)
        self.assertNotIn("sk_live_12345", logs)

        stats = client.get("/api/desktop/reports/stats", headers=headers)
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()["total"], 2)
        self.assertEqual(stats.json()["by_kind"]["bug"], 2)

    def test_client_opt_in_log_collection_and_dedup(self):
        log_dir = os.path.join(self.tmp, "app", "logs", "2026-11-23")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "error.log"), "w", encoding="utf-8") as fh:
            fh.write("[2026-11-23 12:00:00] [ERROR] Failed for bob@test.com Bearer abcdef123456\n")

        with mock.patch.object(desktop_reports, "get_data_path", side_effect=lambda *p: os.path.join(self.tmp, *p)):
            os.environ["LILA_LOG_DIR"] = os.path.join(self.tmp, "app", "logs")
            os.environ["DESKTOP_REPORT_URL"] = "https://reports.example.com/api/desktop"

            settings = desktop_reports.get_report_settings()
            self.assertTrue(settings["configured"])
            self.assertFalse(settings["anonymous_telemetry"])

            disabled_res = desktop_reports.send_anonymous_telemetry()
            self.assertEqual(disabled_res["status"], "disabled")

            updated = desktop_reports.set_telemetry_opt_in(True)
            self.assertTrue(updated["anonymous_telemetry"])

            collected = desktop_reports.collect_recent_logs(max_days=3)
            self.assertNotIn("bob@test.com", collected["logs"])
            self.assertNotIn("abcdef123456", collected["logs"])
            self.assertIn("[email]", collected["logs"])

            calls = []

            def fake_post(url, payload, token="", timeout=8.0):
                calls.append((url, payload))
                return {"ok": True, "status": "stored", "stored": True, "id": 1}

            with mock.patch.object(desktop_reports, "_post_report", side_effect=fake_post):
                first = desktop_reports.send_anonymous_telemetry()
                second = desktop_reports.send_anonymous_telemetry()
                self.assertTrue(first["ok"])
                self.assertEqual(second["status"], "duplicate")
                self.assertEqual(len(calls), 1)

    def test_menu_and_preferences_integration(self):
        fake_webview = types.ModuleType("webview")
        fake_menu_mod = types.ModuleType("webview.menu")
        fake_menu_mod.Menu = _FakeMenu
        fake_menu_mod.MenuAction = _FakeMenuAction
        fake_menu_mod.MenuSeparator = _FakeMenuSeparator
        fake_webview.menu = fake_menu_mod

        with mock.patch.dict("sys.modules", {"webview": fake_webview, "webview.menu": fake_menu_mod}):
            cfg_off = desktop_menu.DesktopMenuConfig(app_name="Todo", report_url="")
            menus_off = desktop_menu.build_desktop_menu(lambda: None, cfg_off, platform_name="win32")
            help_off = [a.title for a in menus_off[-1].items if hasattr(a, "title")]
            self.assertNotIn("Report Bug / Issue...", help_off)

            cfg_on = desktop_menu.DesktopMenuConfig(
                app_name="Todo",
                lang="es",
                report_url="https://example.com/api/desktop",
            )
            menus_on = desktop_menu.build_desktop_menu(lambda: None, cfg_on, platform_name="win32")
            help_on = [a.title for a in menus_on[-1].items if hasattr(a, "title")]
            self.assertIn("Reportar error / bug...", help_on)

            win = _FakeWindow()
            desktop_menu.open_preferences_modal(win, cfg_on)
            self.assertTrue(any("set_telemetry_opt_in" in s for s in win.scripts))

            win2 = _FakeWindow()
            desktop_menu.open_bug_report_modal(win2, cfg_on)
            self.assertTrue(any("send_bug_report" in s for s in win2.scripts))

        bridge = DesktopBridge()
        self.assertIn("anonymous_telemetry", bridge.get_report_settings())


class CoreBugFixesRegressionTests(unittest.TestCase):
    def test_router_no_trailing_slash_on_empty_path(self):
        r = Router(prefix="/api/todos")

        @r.get("")
        async def list_items():
            return []

        @r.get("/")
        async def list_items_slash():
            return []

        paths = [route.path for route in r.get_routes()]
        self.assertEqual(paths, ["/api/todos", "/api/todos/"])

    def test_scaffold_skips_react_scaffold(self):
        tmp = tempfile.mkdtemp(prefix="lila_scaffold_")
        try:
            copy_item("lila", "resources", tmp, "resources")
            self.assertFalse(os.path.exists(os.path.join(tmp, "resources", "react_scaffold")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "resources", "html", "index.jinja")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_lila_client_triggers_full_reload_for_react_pages(self):
        js_path = Path(__file__).resolve().parent.parent / "lila" / "public" / "js" / "lila-client.js"
        content = js_path.read_text(encoding="utf-8")
        self.assertIn('getAttribute("data-layout") === "react"', content)
        self.assertIn("window.location.href = targetUrl", content)

    def test_base_model_allows_explicit_active_zero_and_include_deleted(self):
        tmp = tempfile.mkdtemp(prefix="lila_bm_")
        db_file = os.path.join(tmp, "test.sqlite")
        test_db = Database({"type": "sqlite", "database": db_file, "is_async": True})

        class ItemModel(BaseModel):
            __tablename__ = "test_items_soft_del"
            _connection = test_db
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(80), nullable=False)
            active = Column(Integer, nullable=False, default=1)

        async def _run():
            Cache.clear()
            await test_db.migrate_async(use_base=True, add_columns=False)
            created = await ItemModel.insert_async(name="First", active=1)
            await ItemModel.delete_async(created["id"])

            self.assertIsNone(await ItemModel.get_by_id_async(created["id"]))
            deleted_row = await ItemModel.get_by_id_async(created["id"], include_deleted=True)
            self.assertIsNotNone(deleted_row)
            self.assertEqual(deleted_row["active"], 0)
            self.assertEqual(await ItemModel.count_async(active=0), 1)
            trashed = await ItemModel.get_all_async(active=0)
            self.assertEqual(len(trashed), 1)
            await test_db.close_async()

        try:
            asyncio.run(_run())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_auto_migrate_creates_tables_on_fresh_db(self):
        tmp = tempfile.mkdtemp(prefix="lila_automig_")
        db_file = os.path.join(tmp, "fresh.sqlite")
        test_db = Database({"type": "sqlite", "database": db_file, "is_async": True})

        async def _run():
            import lila.core.admin  # ensure at least Admin table exists on Base.metadata

            ops = await auto_migrate_async(db=test_db, extra_modules=())
            self.assertTrue(any(op["kind"] == "create_table" and op["table"] == "admins" for op in ops))
            await test_db.close_async()

        try:
            asyncio.run(_run())
            con = sqlite3.connect(db_file)
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            con.close()
            self.assertIn("admins", tables)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
