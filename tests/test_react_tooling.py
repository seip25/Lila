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


if __name__ == "__main__":
    unittest.main()
