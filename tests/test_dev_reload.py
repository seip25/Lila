import os
import shutil
import unittest
import uuid

from starlette.testclient import TestClient

from lila.core.app import App, _dev_watch_signature
from lila.core.request import Request
from lila.core.routing import Router
from lila.core.templates import clear_asset_cache, render
from lila.core.translate import Translate


class DevReloadTests(unittest.TestCase):
    def test_watch_signature_changes_with_template_edit(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_reload")
        work = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(os.path.join(work, "resources", "html"), exist_ok=True)
        os.makedirs(os.path.join(work, "public", "js"), exist_ok=True)
        os.makedirs(os.path.join(work, "app", "locales"), exist_ok=True)
        old_cwd = os.getcwd()
        try:
            os.chdir(work)
            template = os.path.join(work, "resources", "html", "index.jinja")
            with open(template, "w", encoding="utf-8") as fh:
                fh.write("<h1>first</h1>")
            with open(os.path.join(work, "public", "js", "app.js"), "w", encoding="utf-8") as fh:
                fh.write("console.log(1);")
            with open(os.path.join(work, "app", "locales", "es.json"), "w", encoding="utf-8") as fh:
                fh.write('{"login": "Entrar"}')

            first = _dev_watch_signature()
            with open(template, "a", encoding="utf-8") as fh:
                fh.write("\n<h1>second</h1>")
            second = _dev_watch_signature()
            self.assertNotEqual(first, second)

            clear_asset_cache()
            Translate.clear_cache()
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(root, ignore_errors=True)

    def test_debug_pages_include_inline_dev_reload(self):
        router = Router()

        @router.get("/")
        async def home(request: Request):
            return render(request, "index.jinja")

        app = App(routes=[router], debug=True, openapi=False, debug_html=False)
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="lila-debug"', response.text)
        self.assertIn("__lilaDevReload", response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")

        client_js = client.get("/js/lila-client.js")
        self.assertEqual(client_js.status_code, 200)
        self.assertIn("__lilaDevReload", client_js.text)


if __name__ == "__main__":
    unittest.main()
