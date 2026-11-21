import json
import os
import shutil
import tempfile
import unittest
import xml.dom.minidom
from typing import Literal, Optional

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Boolean, Column, Integer, String
from starlette.testclient import TestClient

from lila.cli import installers
from lila.cli.auth import REACT_PAGE_REPLACEMENTS, reactify_route, read_file
from lila.cli.react import _scaffold_files
from lila.core.app import App
from lila.core.base_model import BaseModel as LilaModel
from lila.core.react import react_render
from lila.core.routing import Router
from lila.core.typescript import pydantic_interfaces, table_interface
from lila.core.vite import ViteBridge, default_entry
from lila.testing import override_env


class AuthReactTests(unittest.TestCase):
    def test_every_page_handler_becomes_react(self):
        folder = {"dashboard.py": "routes", "profile.py": "routes"}
        for filename in REACT_PAGE_REPLACEMENTS:
            source = read_file(f"cli/auth/{folder.get(filename, 'routes')}/{filename}")
            out = reactify_route(filename, source)
            compile(out, filename, "exec")
            self.assertIn("react_render(", out)
            self.assertNotIn("from lila.core.templates import render", out)
            self.assertNotIn(" render(request", out)
            if "configured_providers" in out:
                self.assertIn("from lila.core.oauth import OAuth", out)

    def test_react_pages_exist_for_every_component(self):
        base = os.path.join(os.path.dirname(__file__), "..", "lila", "cli", "auth", "react", "pages")
        for replacements in REACT_PAGE_REPLACEMENTS.values():
            for _old, new in replacements:
                component = new.split('react_render(request, "', 1)[1].split('"', 1)[0]
                self.assertTrue(os.path.isfile(os.path.join(base, component + ".tsx")), component)


class ScaffoldTests(unittest.TestCase):
    def test_typescript_is_default_and_js_shares_the_client(self):
        ts = {rel for _src, rel in _scaffold_files("ts")}
        js = {rel for _src, rel in _scaffold_files("js")}
        self.assertIn("tsconfig.json", ts)
        self.assertIn("vite.config.ts", ts)
        self.assertIn(os.path.join("resources", "react", "main.tsx"), ts)
        self.assertIn(os.path.join("resources", "react", "main.jsx"), js)
        shared = os.path.join("resources", "react", "lila", "index.tsx")
        self.assertIn(shared, ts)
        self.assertIn(shared, js)
        self.assertIn(os.path.join("app", "routes", "web", "react_pages.py"), js)


class Address(BaseModel):
    city: str


class Signup(BaseModel):
    email: str
    password: str = Field(min_length=8, description="Secret */ value")
    role: Literal["admin", "user"] = "user"
    tags: list = []
    address: Optional[Address] = None


class TsTable(LilaModel):
    __tablename__ = "ts_tooling_table"
    __private_fields__ = ("password",)
    id = Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)
    password = Column(String(50))
    enabled = Column(Boolean)
    data = Column(JSON)


class TypeScriptTests(unittest.TestCase):
    def test_pydantic_interfaces(self):
        out = "\n".join(pydantic_interfaces([("Signup", Signup)]))
        self.assertIn("export interface Address {\n  city: string;\n}", out)
        self.assertIn('role?: "admin" | "user";', out)
        self.assertIn("address?: Address | null;", out)
        self.assertIn("/** Secret * / value */", out)

    def test_table_interface_hides_private_fields(self):
        out = table_interface(TsTable)
        self.assertIn("id: number;", out)
        self.assertIn("name: string;", out)
        self.assertIn("enabled: boolean | null;", out)
        self.assertIn("data: unknown;", out)
        self.assertNotIn("password", out)


class InstallerTests(unittest.TestCase):
    def test_wix_source_is_valid_xml_with_icon_and_shortcuts(self):
        source = installers.wix_source("My_App", "dist/My_App.exe", "2.1.0-beta", "Acme & Co", "public/favicon.ico", "com.acme.app")
        xml.dom.minidom.parseString(source)
        self.assertIn('Version="2.1.0"', source)
        self.assertIn('ARPPRODUCTICON', source)
        self.assertIn('Id="DesktopLink"', source)
        self.assertIn("Acme &amp; Co", source)
        onedir = installers.wix_source("X", "dist/X/X.exe", onedir="dist/X", desktop_shortcut=False)
        xml.dom.minidom.parseString(onedir)
        self.assertIn("<Files Directory=\"INSTALLFOLDER\"", onedir)
        self.assertNotIn("DesktopShortcut", onedir)

    def test_versions_and_upgrade_codes(self):
        self.assertEqual(installers.msi_version("v2"), "2.0.0")
        self.assertEqual(installers.msi_version(""), "1.0.0")
        self.assertEqual(installers.msi_version("300.1.70000"), "255.1.65535")
        self.assertEqual(installers.upgrade_code("com.a"), installers.upgrade_code("com.a"))
        self.assertNotEqual(installers.upgrade_code("com.a"), installers.upgrade_code("com.b"))

    def test_commands(self):
        self.assertEqual(installers.dmg_command("s", "dist/A.dmg", "A")[:2], ["hdiutil", "create"])
        self.assertEqual(installers.wix_command("a.wxs", "dist/A.msi")[:2], ["wix", "build"])
        self.assertEqual(installers.default_installer("win32"), "msi")
        self.assertEqual(installers.default_installer("darwin"), "dmg")
        self.assertIsNone(installers.default_installer("linux"))

    def test_png_icon_is_converted_for_windows(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed")
        folder = tempfile.mkdtemp()
        try:
            ico = installers.convert_icon(installers.package_icon(), "win32", work_dir=folder)
            self.assertTrue(ico.endswith(".ico") and os.path.isfile(ico))
            self.assertEqual(installers.convert_icon("x.ico", "win32", work_dir=folder), "x.ico")
        finally:
            shutil.rmtree(folder, ignore_errors=True)


router = Router()


@router.get("/t")
async def translated(request):
    return react_render(request, "Auth/Login", {}, translations=["login", "missing_key"])


class ReactExtrasTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)
        os.makedirs(os.path.join("public", "build", ".vite"))
        with open(os.path.join("public", "build", ".vite", "manifest.json"), "w") as fh:
            json.dump({"resources/react/main.tsx": {"file": "assets/m.js", "isEntry": True}}, fh)
        ViteBridge.reset()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)
        ViteBridge.reset()

    def test_default_entry_and_translations(self):
        with override_env(DEBUG="False"):
            self.assertEqual(default_entry(), "resources/react/main.tsx")
            client = TestClient(App(routes=[router], rate_limit=None, debug=False))
            page = client.get("/t", headers={"X-Lila-React": "1"}).json()
        self.assertIn("login", page["t"])
        self.assertEqual(page["t"]["missing_key"], "missing_key")

    def test_dev_reload_script_only_in_debug(self):
        with override_env(DEBUG="False"):
            body = TestClient(App(routes=[router], rate_limit=None, debug=False)).get("/t").text
        self.assertNotIn("__lilaDevReload", body)
        with override_env(DEBUG="True"):
            body = TestClient(App(routes=[router], rate_limit=None, debug=True)).get("/t").text
        self.assertIn("__lilaDevReload", body)


def _load_me_router():
    import importlib.util

    path = os.path.join(os.path.dirname(__file__), "..", "lila", "cli", "auth", "routes", "me.py")
    spec = importlib.util.spec_from_file_location("lila_scaffold_me", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.router


class AuthMeTests(unittest.TestCase):
    def test_me_endpoint_exposes_only_public_fields(self):
        from lila.testing import login

        client = TestClient(App(routes=[_load_me_router()], rate_limit=None, debug=False))
        anonymous = client.get("/api/auth/me").json()
        self.assertIsNone(anonymous["user"])
        self.assertEqual(client.get("/api/auth/me").headers["cache-control"], "no-store")
        login(client, {"user_id": 7, "email": "ana@example.com", "name": "Ana", "role": "admin", "secret_note": "x"})
        data = client.get("/api/auth/me").json()
        self.assertEqual(data["user"]["id"], 7)
        self.assertEqual(data["user"]["name"], "Ana")
        self.assertEqual(data["roles"], ["admin"])
        self.assertNotIn("secret_note", data["user"])

    def test_auth_scaffold_registers_me_route(self):
        init = read_file("cli/auth/routes/auth_init.py")
        self.assertIn("_me_routes", init)


class UiKitTests(unittest.TestCase):
    KIT = ("Button.tsx", "Form.tsx", "Card.tsx", "Badge.tsx", "Dialog.tsx", "Carousel.tsx", "Toast.tsx",
           "Theme.tsx", "Feedback.tsx", "DataTable.tsx", "index.ts", "ui.css")

    def test_kit_ships_in_both_variants(self):
        for variant in ("ts", "js"):
            files = {rel for _src, rel in _scaffold_files(variant)}
            for name in self.KIT:
                self.assertIn(os.path.join("resources", "react", "components", "ui", name), files)
            for name in ("index.tsx", "auth.tsx", "router.tsx"):
                self.assertIn(os.path.join("resources", "react", "lila", name), files)

    def test_kit_css_uses_lila_palette(self):
        css_path = os.path.join(os.path.dirname(__file__), "..", "lila", "resources", "react_scaffold", "common",
                                "resources", "react", "components", "ui", "ui.css")
        with open(css_path, encoding="utf-8") as fh:
            css = fh.read()
        for token in ("--lila-primary", ".btn-primary", ".form-control", ".card", "data-theme", ".badge", ".table-lila"):
            self.assertIn(token, css)

    def test_copy_ui_only_writes_missing_files(self):
        from lila.cli.react import copy_ui

        cwd = os.getcwd()
        folder = tempfile.mkdtemp()
        try:
            os.chdir(folder)
            first = copy_ui(quiet=True)
            self.assertTrue(any(path.endswith("Button.tsx") for path in first))
            target = os.path.join("resources", "react", "components", "ui", "Button.tsx")
            with open(target, "w") as fh:
                fh.write("// mine")
            self.assertEqual(copy_ui(quiet=True), [])
            with open(target) as fh:
                self.assertEqual(fh.read(), "// mine")
        finally:
            os.chdir(cwd)
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


class DesktopUpdateAndSigningTests(unittest.TestCase):
    def test_versions_and_manifest_check(self):
        import http.server
        import threading

        from lila.core.desktop_bridge import check_update, parse_version, platform_key

        self.assertGreater(parse_version("1.10.0"), parse_version("1.9.9"))
        self.assertEqual(parse_version("v2"), (2, 0, 0))
        manifest = json.dumps({"version": "1.5.0", "notes": "Fixes",
                               "files": {platform_key(): {"url": "https://x/app.bin", "sha256": "a" * 64}}}).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.end_headers()
                self.wfile.write(manifest)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/latest.json"
            self.assertTrue(check_update(url, "1.4.9")["available"])
            self.assertFalse(check_update(url, "1.5.0")["available"])
        finally:
            server.shutdown()
        self.assertFalse(check_update("http://example.com/latest.json", "1.0")["available"])  # https only
        self.assertFalse(check_update(None, "1.0")["available"])

    def test_download_rejects_bad_checksum_and_http(self):
        from lila.core.desktop_bridge import download_verified

        with self.assertRaises(ValueError):
            download_verified("http://example.com/x.msi", "a" * 64)
        with self.assertRaises(ValueError):
            download_verified("https://example.com/x.msi", "short")

    def test_open_external_only_allows_web_links(self):
        from lila.core.desktop_bridge import DesktopBridge

        bridge = DesktopBridge()
        self.assertFalse(bridge.open_external("file:///etc/passwd"))
        self.assertFalse(bridge.open_external("javascript:alert(1)"))

    def test_signing_commands(self):
        cmd = installers.macos_sign_command("dist/App.app", "Developer ID Application: Acme (TEAM)")
        self.assertEqual(cmd[:3], ["codesign", "--deep", "--force"])
        self.assertIn("runtime", cmd)
        self.assertEqual(installers.macos_notarize_commands("dist/App.dmg", "prof")[1], ["xcrun", "stapler", "staple", "dist/App.dmg"])
        with override_env(WINDOWS_SIGN_PASSWORD="hunter2"):
            cmd = installers.windows_sign_command("dist/App.msi", cert="cert.pfx")
        self.assertEqual(cmd[cmd.index("/f") + 1], "cert.pfx")
        self.assertNotIn("hunter2", installers.redact(cmd))
        self.assertIn("/sha1", installers.windows_sign_command("a.exe", thumbprint="ABC"))
        self.assertIn("/a", installers.windows_sign_command("a.exe"))

    def test_release_manifest_merges_platforms(self):
        folder = tempfile.mkdtemp()
        try:
            msi = os.path.join(folder, "App.msi")
            dmg = os.path.join(folder, "App.dmg")
            for path in (msi, dmg):
                with open(path, "wb") as fh:
                    fh.write(path.encode())
            win = installers.build_update_manifest("1.2.0", "https://dl.example/app/", [msi])
            both = installers.build_update_manifest("1.2.0", "https://dl.example/app", [dmg], previous=win)
            self.assertEqual(set(both["files"]), {"windows", "macos"})
            self.assertEqual(both["files"]["macos"]["url"], "https://dl.example/app/App.dmg")
            self.assertEqual(len(both["files"]["windows"]["sha256"]), 64)
            fresh = installers.build_update_manifest("1.3.0", "https://dl.example/app", [dmg], previous=both)
            self.assertEqual(set(fresh["files"]), {"macos"})
        finally:
            shutil.rmtree(folder, ignore_errors=True)
