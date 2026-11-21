import builtins
import os
import unittest

from lila.core import static

JS_DIR = os.path.join(os.path.dirname(__file__), "..", "lila", "public", "js")


class ShippedMinifiedClientTests(unittest.TestCase):
    def test_min_files_match_their_sources(self):
        """Edited lila-client.js/ws.js? Run `python -m lila.core.static`."""
        for name in ("lila-client.js", "ws.js"):
            path = os.path.join(JS_DIR, name)
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            shipped = static._shipped_min(path, source)
            self.assertIsNotNone(shipped, f"{name}.min is stale: run python -m lila.core.static")
            self.assertLess(len(shipped), len(source) * 0.85)

    def test_used_without_rjsmin(self):
        path = os.path.join(JS_DIR, "lila-client.js")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "rjsmin":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            out = static._minify_js(source, path)
        finally:
            builtins.__import__ = real_import
        self.assertTrue(out.startswith("/*! Lila lila-client.js"))

    def test_stale_min_is_ignored(self):
        path = os.path.join(JS_DIR, "lila-client.js")
        self.assertIsNone(static._shipped_min(path, "different source"))


if __name__ == "__main__":
    unittest.main()
