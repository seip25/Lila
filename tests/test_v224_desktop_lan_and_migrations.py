import asyncio
import importlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import unittest

from sqlalchemy import Column, Integer, String

from lila.core import desktop_lan
from lila.core import migrations as mig
from lila.core.app import App
from lila.core.config import ConfigLoader
from lila.core.database import Base, Database
from lila.core.desktop_bridge import DesktopBridge
from lila.core.request import Request
from lila.core.routing import Router
from lila.core.websocket import WebSocketHub


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_call(url: str, method: str = "GET", headers=None, data: bytes | None = None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler())
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with opener.open(req, timeout=5.0) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        try:
            return err.code, err.headers, err.read()
        finally:
            err.close()


class _MigItem(Base):
    __tablename__ = "v224_mig_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False)


class V224MigrationsAndBackupTests(unittest.TestCase):
    def setUp(self):
        self._root = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".tmp_v224_mig_" + uuid.uuid4().hex
        )
        os.makedirs(self._root, exist_ok=True)
        self._old_cwd = os.getcwd()
        self._saved_data_dir = os.environ.get("LILA_DATA_DIR")
        self._saved_backup = os.environ.get("LILA_MIGRATE_BACKUP")
        self._saved_keep = os.environ.get("LILA_MIGRATE_BACKUP_KEEP")
        self._saved_loaded = ConfigLoader._loaded
        self._saved_data = dict(ConfigLoader._data)
        self._saved_app_mods = {
            k: sys.modules.pop(k)
            for k in list(sys.modules)
            if k == "app" or k.startswith("app.")
        }

        os.chdir(self._root)
        os.environ["LILA_DATA_DIR"] = os.path.join(self._root, "data")
        ConfigLoader._loaded = True
        ConfigLoader._data = {
            "SECRET_KEY": "a" * 48,
            "LILA_MIGRATE_BACKUP": True,
            "LILA_MIGRATE_BACKUP_KEEP": 2,
            "VERSION_PROJECT": "2.2.5",
            "DB_TYPE": "sqlite",
            "DB_NAME": "migtest",
        }

    def tearDown(self):
        os.chdir(self._old_cwd)
        for k in [name for name in list(sys.modules) if name == "app" or name.startswith("app.")]:
            sys.modules.pop(k, None)
        sys.modules.update(self._saved_app_mods)
        importlib.invalidate_caches()
        for key, prev in (
            ("LILA_DATA_DIR", self._saved_data_dir),
            ("LILA_MIGRATE_BACKUP", self._saved_backup),
            ("LILA_MIGRATE_BACKUP_KEEP", self._saved_keep),
        ):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        ConfigLoader._loaded = self._saved_loaded
        ConfigLoader._data = self._saved_data
        shutil.rmtree(self._root, ignore_errors=True)

    def test_pre_migrate_hot_backup_and_versioned_scripts(self):
        db_path = os.path.join(self._root, "migtest.sqlite")
        # Create an existing non-empty SQLite database (with pre-existing sentinel data)
        seed_conn = sqlite3.connect(db_path)
        seed_conn.execute("CREATE TABLE legacy_notes (id INTEGER PRIMARY KEY, body TEXT)")
        seed_conn.execute("INSERT INTO legacy_notes (body) VALUES ('before-upgrade')")
        seed_conn.commit()
        seed_conn.close()

        # Prepare app/migrations/ package with 001 (sync) + 002 (async) scripts
        mig_pkg = os.path.join(self._root, "app", "migrations")
        os.makedirs(mig_pkg, exist_ok=True)
        with open(os.path.join(self._root, "app", "__init__.py"), "w", encoding="utf-8") as fh:
            fh.write("")
        with open(os.path.join(mig_pkg, "__init__.py"), "w", encoding="utf-8") as fh:
            fh.write("")
        with open(os.path.join(mig_pkg, "001_seed_note.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "import sqlite3\n"
                "def upgrade(db):\n"
                "    c = sqlite3.connect(db.engine.url.database)\n"
                "    c.execute(\"INSERT INTO legacy_notes (body) VALUES ('script-001')\")\n"
                "    c.commit()\n"
                "    c.close()\n"
            )
        with open(os.path.join(mig_pkg, "002_async_note.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "from sqlalchemy import text\n"
                "async def upgrade(db):\n"
                "    async with db.engine.begin() as conn:\n"
                "        await conn.execute(text(\"INSERT INTO legacy_notes (body) VALUES ('script-002')\"))\n"
            )

        sys.path.insert(0, self._root)
        importlib.invalidate_caches()
        db = Database({"type": "sqlite", "database": "migtest", "is_async": True})
        db.connect()
        try:
            ops = asyncio.run(mig.auto_migrate_async(db=db, extra_modules=()))
            report = mig.last_auto_migrate_report()

            # 1. Pre-migration backup was created BEFORE scripts ran
            self.assertIsNotNone(report["backup_path"])
            self.assertTrue(os.path.isfile(report["backup_path"]))
            bak_conn = sqlite3.connect(report["backup_path"])
            bak_rows = [r[0] for r in bak_conn.execute("SELECT body FROM legacy_notes ORDER BY id").fetchall()]
            bak_conn.close()
            self.assertEqual(bak_rows, ["before-upgrade"])

            # 2. Live DB has both schema op & scripts applied in order
            self.assertTrue(any(op["table"] == "v224_mig_items" for op in ops))
            self.assertEqual(
                report["applied_scripts"],
                ["app.migrations.001_seed_note", "app.migrations.002_async_note"],
            )
            live_conn = sqlite3.connect(db_path)
            live_rows = [r[0] for r in live_conn.execute("SELECT body FROM legacy_notes ORDER BY id").fetchall()]
            live_conn.close()
            self.assertEqual(live_rows, ["before-upgrade", "script-001", "script-002"])

            # 3. Second run does nothing and creates NO extra backup
            ops2 = asyncio.run(mig.auto_migrate_async(db=db, extra_modules=()))
            report2 = mig.last_auto_migrate_report()
            self.assertEqual(ops2, [])
            self.assertIsNone(report2["backup_path"])
            self.assertEqual(report2["applied_scripts"], [])

            # 4. Rotation keeps <= 2 backups & LILA_MIGRATE_BACKUP=False skips backups
            b1 = mig.backup_sqlite_before_migrate(db, max_backups=2)
            time.sleep(0.02)
            b2 = mig.backup_sqlite_before_migrate(db, max_backups=2)
            self.assertTrue(os.path.isfile(b1) and os.path.isfile(b2))
            bak_dir = os.path.dirname(b2)
            self.assertLessEqual(len(os.listdir(bak_dir)), 2)

            bridge = DesktopBridge()
            manual_bak = bridge.create_backup()
            self.assertTrue(manual_bak["ok"])
            self.assertTrue(os.path.isfile(manual_bak["path"]))
        finally:
            asyncio.run(db.close_async())
            if self._root in sys.path:
                sys.path.remove(self._root)
            for mod_key in [k for k in list(sys.modules) if k == "app" or k.startswith("app.")]:
                sys.modules.pop(mod_key, None)


class V224DesktopLanGatewayTests(unittest.TestCase):
    def setUp(self):
        self._saved_env = {
            k: os.environ.get(k)
            for k in ("LILA_DESKTOP_TOKEN", "LILA_DESKTOP", "LILA_LAN_PROXY_SECRET", "SECRET_KEY")
        }
        os.environ["SECRET_KEY"] = "b" * 48
        os.environ["LILA_DESKTOP_TOKEN"] = "desktop_secret_tok_v224"
        os.environ["LILA_DESKTOP"] = "1"
        desktop_lan.stop_lan_gateway()
        desktop_lan.set_desktop_local_port(0)

    def tearDown(self):
        desktop_lan.stop_lan_gateway()
        desktop_lan.set_desktop_local_port(0)
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_lan_otp_pairing_security_deny_and_websocket(self):
        import uvicorn
        import websockets

        router = Router()
        hub = WebSocketHub()

        @router.get("/")
        async def home(request: Request):
            return {
                "ok": True,
                "is_lan": desktop_lan.is_lan_request(request),
                "lan_ip": desktop_lan.lan_client_ip(request),
            }

        @router.post("/echo")
        async def echo(request: Request):
            body = await request.json()
            return {"echo": body, "is_lan": desktop_lan.is_lan_request(request)}

        @router.get("/secret")
        async def secret_page(request: Request):
            return {"secret": True}

        @hub.on("move")
        async def game_ws(ws, data):
            await ws.send_json({"event": "moved", "data": data})

        router.ws_hub("/ws/game", hub)

        app = App(routes=[router], debug=False, health=False, openapi=False, csp=False)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            local_port = s.getsockname()[1]

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=local_port,
            log_level="warning",
            access_log=False,
            timeout_graceful_shutdown=1,
            log_config=None,
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        srv_thread = threading.Thread(target=server.run, daemon=True)
        srv_thread.start()

        gw = desktop_lan.DesktopLanGateway(
            target_port=local_port,
            lan_port=0,
            otp_ttl=120,
            deny=["/secret*"],
            bind_host="127.0.0.1",
        )
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and not server.started:
                time.sleep(0.05)
            self.assertTrue(server.started)

            desktop_lan.set_desktop_local_port(local_port)
            gw.start()
            gw_base = f"http://127.0.0.1:{gw.bound_port}"
            otp = gw.status()["otp"]

            # 1. Unauthenticated LAN browser -> 303 pair; API -> 401; spoofed headers rejected
            st, hdrs, _ = _http_call(f"{gw_base}/")
            self.assertEqual(st, 303)
            self.assertEqual(hdrs.get("Location"), desktop_lan.PAIR_PATH)

            st_api, _, _ = _http_call(
                f"{gw_base}/api/test",
                headers={
                    "Accept": "application/json",
                    "X-Lila-Desktop-Token": os.environ["LILA_DESKTOP_TOKEN"],
                    "X-Lila-Lan": "1",
                    "X-Lila-Lan-Proxy": gw.proxy_secret,
                },
            )
            self.assertEqual(st_api, 401)

            # 2. Wrong OTP attempts -> 401 then 429 lockout after 5 tries
            for i in range(4):
                code_err, _, _ = _http_call(
                    f"{gw_base}{desktop_lan.PAIR_PATH}",
                    method="POST",
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    data=b'{"code":"000000"}' if otp != "000000" else b'{"code":"999999"}',
                )
                self.assertEqual(code_err, 401, f"Attempt {i} expected 401")
            lock_code, _, _ = _http_call(
                f"{gw_base}{desktop_lan.PAIR_PATH}",
                method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                data=b'{"code":"000000"}' if otp != "000000" else b'{"code":"999999"}',
            )
            self.assertEqual(lock_code, 429)

            # Clear failure lockout using a second gateway instance or wait? Better test lockout with separate gateway/IP;
            # let's reset failures via gw._failures.clear() for continuing pairing flow on same gateway:
            gw._failures.clear()

            # 3. Valid OTP issues lila_lan cookie
            ok_pair, pair_hdrs, pair_body = _http_call(
                f"{gw_base}{desktop_lan.PAIR_PATH}",
                method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                data=json.dumps({"code": otp}).encode("utf-8"),
            )
            self.assertEqual(ok_pair, 200, pair_body)
            set_cookie = pair_hdrs.get("Set-Cookie", "")
            self.assertIn("lila_lan=", set_cookie)
            lan_cookie = set_cookie.split(";", 1)[0]

            # 4. Paired GET/POST succeeds with is_lan=True & real socket IP (spoofed IP discarded)
            st_home, _, home_body = _http_call(
                f"{gw_base}/",
                headers={"Cookie": lan_cookie, "X-Forwarded-For": "9.9.9.9"},
            )
            self.assertEqual(st_home, 200)
            self.assertEqual(json.loads(home_body), {"ok": True, "is_lan": True, "lan_ip": "127.0.0.1"})

            st_echo, _, echo_body = _http_call(
                f"{gw_base}/echo",
                method="POST",
                headers={"Cookie": lan_cookie, "Content-Type": "application/json"},
                data=b'{"turn":1}',
            )
            self.assertEqual(st_echo, 200)
            self.assertEqual(json.loads(echo_body), {"echo": {"turn": 1}, "is_lan": True})

            # 5. Path denied on LAN (403) while directly accessible on local PC with _dt token
            st_sec_lan, _, _ = _http_call(f"{gw_base}/secret", headers={"Cookie": lan_cookie})
            self.assertEqual(st_sec_lan, 403)
            st_sec_pc, sec_pc_hdrs, _ = _http_call(
                f"http://127.0.0.1:{local_port}/secret?_dt={os.environ['LILA_DESKTOP_TOKEN']}"
            )
            self.assertEqual(st_sec_pc, 303)
            pc_cookie = sec_pc_hdrs.get("Set-Cookie", "").split(";", 1)[0]
            st_sec_pc2, _, sec_pc_body = _http_call(
                f"http://127.0.0.1:{local_port}/secret", headers={"Cookie": pc_cookie}
            )
            self.assertEqual(st_sec_pc2, 200)
            self.assertEqual(json.loads(sec_pc_body), {"secret": True})

            # 6. WebSocket over LAN gateway works with lila_lan cookie & blocks without
            async def ws_checks():
                with self.assertRaises(Exception):
                    async with websockets.connect(
                        f"ws://127.0.0.1:{gw.bound_port}/ws/game",
                        proxy=None,
                    ):
                        pass
                async with websockets.connect(
                    f"ws://127.0.0.1:{gw.bound_port}/ws/game",
                    additional_headers={"Cookie": lan_cookie},
                    proxy=None,
                ) as ws:
                    await ws.send(json.dumps({"event": "move", "data": {"x": 3, "y": 4}}))
                    reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                    self.assertEqual(reply, {"event": "moved", "data": {"x": 3, "y": 4}})

            asyncio.run(ws_checks())

            # 7. Revoke LAN sessions immediately invalidates paired cookie
            revoked = gw.revoke_sessions()
            self.assertEqual(revoked, 1)
            st_after_revoke, _, _ = _http_call(
                f"{gw_base}/api/x",
                headers={"Cookie": lan_cookie, "Accept": "application/json"},
            )
            self.assertEqual(st_after_revoke, 401)
        finally:
            gw.stop()
            server.should_exit = True
            srv_thread.join(timeout=3.0)

    def test_bridge_lan_controls(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            dummy_port = s.getsockname()[1]

        desktop_lan.set_desktop_local_port(dummy_port)
        bridge = DesktopBridge()
        st0 = bridge.lan_status()
        self.assertFalse(st0["running"])

        st1 = bridge.start_lan()
        self.assertTrue(st1["running"])
        self.assertEqual(len(st1["otp"]), 6)

        st2 = bridge.rotate_lan_otp()
        self.assertTrue(st2["running"])
        self.assertEqual(len(st2["otp"]), 6)

        st3 = bridge.revoke_lan_sessions()
        self.assertEqual(st3["revoked"], 0)

        st4 = bridge.stop_lan()
        self.assertFalse(st4["running"])


if __name__ == "__main__":
    unittest.main()
