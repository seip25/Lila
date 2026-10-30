import os
import shutil
import uuid
import unittest

from lila.cli._patch import add_import, add_includes, find_matching_paren, patch_main


def _tmpdir() -> str:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_cli")
    path = os.path.join(root, uuid.uuid4().hex)
    os.makedirs(path, exist_ok=True)
    return path


class PatchTests(unittest.TestCase):
    def test_find_matching_paren_ignores_comments_and_strings(self):
        source = 'app = App(\n  x=1,  # comment )\n  y=")",\n)\nnext_line'
        start = source.index("(")
        end = find_matching_paren(source, start)
        self.assertEqual(source[end - 1], ")")
        self.assertIn("next_line", source[end:])

    def test_includes_are_placed_after_complete_app_call(self):
        source = (
            "from lila.core.app import App\n"
            "app = App(\n"
            "    routes=[],\n"
            "    rate_limit=300,  # 300 req/min (None to disable)\n"
            ")\n"
            "\ndef main():\n"
            "    pass\n"
        )
        updated = add_includes(source, "app.include_router(x)")
        compile(updated, "main.py", "exec")
        self.assertGreater(updated.index("app.include_router(x)"), updated.index("None to disable"))
        self.assertLess(updated.index("app.include_router(x)"), updated.index("def main"))

    def test_patch_main_never_writes_broken_python(self):
        source = (
            "from lila.core.app import App\n"
            "app = App(\n"
            "    rate_limit=300,  # (None para desactivar)\n"
            ")\n"
        )
        tmp = _tmpdir()
        try:
            path = os.path.join(tmp, "main.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source)
            changed = patch_main(path, "from x import y", "app.include_router(y)")
            self.assertTrue(changed)
            with open(path, "r", encoding="utf-8") as fh:
                result = fh.read()
            compile(result, path, "exec")
            self.assertIn("app.include_router(y)", result)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
