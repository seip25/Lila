import gzip
import hashlib
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.cache import Cache
from lila.core.routing import Router
from lila.core.static import LilaStaticFiles, accepted_encoding, clear_cache


class StaticCompressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "app.js"), "w") as fh:
            fh.write("console.log('lila');\n" * 400)
        with open(os.path.join(self.tmp, "pic.png"), "wb") as fh:
            fh.write(b"\x89PNG" + b"0" * 4000)
        clear_cache()
        self.client = TestClient(Starlette(routes=[Mount("/s", LilaStaticFiles(directory=self.tmp))]))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_text_assets_are_compressed_once_and_cached(self):
        res = self.client.get("/s/app.js", headers={"accept-encoding": "gzip"})
        self.assertEqual(res.headers.get("content-encoding"), "gzip")
        self.assertIn("Accept-Encoding", res.headers.get("vary", ""))
        self.assertEqual(res.text, "console.log('lila');\n" * 400)
        etag = res.headers["etag"]
        again = self.client.get("/s/app.js", headers={"accept-encoding": "gzip", "if-none-match": etag})
        self.assertIn(again.status_code, (200, 304))

    def test_images_are_not_compressed(self):
        res = self.client.get("/s/pic.png", headers={"accept-encoding": "gzip"})
        self.assertIsNone(res.headers.get("content-encoding"))

    def test_precompressed_sibling_is_served(self):
        path = os.path.join(self.tmp, "app.js")
        with open(path + ".gz", "wb") as fh:
            fh.write(gzip.compress(b"PRE"))
        os.utime(path + ".gz", (os.path.getmtime(path) + 5,) * 2)
        res = self.client.get("/s/app.js", headers={"accept-encoding": "gzip"})
        self.assertEqual(res.text, "PRE")

    def test_accept_encoding_parsing(self):
        self.assertEqual(accepted_encoding("gzip, deflate"), "gzip")
        self.assertIsNone(accepted_encoding("gzip;q=0, identity"))
        self.assertIsNone(accepted_encoding(""))


class BundledJsAndETagTests(unittest.TestCase):
    def setUp(self):
        router = Router()

        @router.get("/page")
        async def page(request):
            return {"hello": "world"}

        self.client = TestClient(App(routes=[router], debug=False, rate_limit=None, gzip=True))

    def test_client_js_minified_compressed_and_304(self):
        res = self.client.get("/js/lila-client.js", headers={"accept-encoding": "gzip"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-encoding"), "gzip")
        raw_size = os.path.getsize(os.path.join(os.path.dirname(__file__), "..", "lila", "public", "js", "lila-client.js"))
        self.assertLess(len(res.content), raw_size)
        cached = self.client.get("/js/lila-client.js", headers={"accept-encoding": "gzip", "if-none-match": res.headers["etag"]})
        self.assertEqual(cached.status_code, 304)

    def test_dynamic_json_gets_etag_and_304(self):
        first = self.client.get("/page")
        tag = first.headers.get("etag")
        self.assertTrue(tag and tag.startswith('W/"'))
        second = self.client.get("/page", headers={"if-none-match": tag})
        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.content, b"")


class CacheBudgetTests(unittest.TestCase):
    def tearDown(self):
        Cache.configure("memory")

    def test_memory_budget_in_mb_keeps_sessions(self):
        Cache.configure("memory", {"max_mb": 0.05, "max_items": 10000})
        Cache.clear(include_sessions=True)
        Cache.set("session:keep", {"user": 1}, ttl=60)
        for i in range(300):
            Cache.set(f"route:{i}", "x" * 1000, ttl=60)
        self.assertLessEqual(Cache._DATA.total_bytes, Cache._MAX_BYTES)
        self.assertEqual(Cache.get("session:keep"), {"user": 1})
        Cache.delete("route:*")
        Cache.delete("session:keep")
        self.assertEqual(Cache._DATA.total_bytes, 0)


class TailwindTemplateTests(unittest.TestCase):
    def test_compiled_css_replaces_runtime_in_production(self):
        from lila.core import templates as tpl

        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                tpl.clear_asset_cache()
                html_runtime = tpl.jinja_env.get_template("lila/tailwind.jinja").render(csrf_token="x")
                self.assertIn("js/tailwind.js", html_runtime)
                os.makedirs(os.path.join("public", "css"))
                with open(os.path.join("public", "css", "lila.css"), "w") as fh:
                    fh.write("a{}")
                tpl.clear_asset_cache()
                with mock.patch.object(tpl, "is_debug", return_value=False):
                    html = tpl.jinja_env.get_template("lila/tailwind.jinja").render(csrf_token="x")
                self.assertIn('/css/lila.css', html)
                self.assertNotIn("js/tailwind.js", html)
                self.assertNotIn("text/tailwindcss", html)
            finally:
                tpl.clear_asset_cache()
                os.chdir(cwd)


class TailwindBuildTests(unittest.TestCase):
    def test_binary_download_is_verified(self):
        from lila.cli import css

        payload = b"#!/bin/sh\necho fake\n"
        good = hashlib.sha256(payload).hexdigest()
        asset = css.asset_name()

        def fake_download(url, timeout=120):
            if url.endswith("sha256sums.txt"):
                return f"{good}  ./{asset}\n".encode()
            return payload

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp, "LOCALAPPDATA": tmp}):
            os.environ.pop("TAILWIND_BIN", None)
            path = css.ensure_binary("9.9.9", downloader=fake_download)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR)

            def bad_download(url, timeout=120):
                if url.endswith("sha256sums.txt"):
                    return f"{'0' * 64}  {asset}\n".encode()
                return payload

            with self.assertRaises(RuntimeError):
                css.ensure_binary("9.9.8", downloader=bad_download)

    def test_input_contains_sources_and_theme(self):
        from lila.cli.css import build_input

        text = build_input(".")
        self.assertIn('@import "tailwindcss" source(none);', text)
        self.assertIn("lila-client.js", text)
        self.assertIn("@theme", text)

    @unittest.skipIf(sys.platform.startswith("win"), "shell script binary")
    def test_build_command_with_fake_binary(self):
        from typer.testing import CliRunner
        from lila.cli.css import app as css_app

        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "tailwindcss")
            with open(fake, "w") as fh:
                fh.write('#!/bin/sh\nwhile [ "$1" ]; do if [ "$1" = "-o" ]; then shift; echo "a{b:c}" > "$1"; fi; shift; done\n')
            os.chmod(fake, 0o755)
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with mock.patch.dict(os.environ, {"TAILWIND_BIN": fake}):
                    result = CliRunner().invoke(css_app, ["build"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertTrue(os.path.isfile(os.path.join(tmp, "public", "css", "lila.css.gz")))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
