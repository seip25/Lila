import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from lila.cli.desktop import DesktopBridge, app as desktop_cli
from lila.core import desktop_menu
from lila.core.config import ConfigLoader


class _FakeWindow:
    def __init__(self, prevent_default: bool = False, selected: str = ""):
        self.scripts = []
        self.prevent_default = prevent_default
        self.selected = selected
        self.fullscreen_toggles = 0
        self.destroyed = False

    def evaluate_js(self, script: str):
        self.scripts.append(script)
        if "window.dispatchEvent(ev)" in script:
            return self.prevent_default
        if "selectionStart" in script:
            return self.selected
        return None

    def toggle_fullscreen(self):
        self.fullscreen_toggles += 1

    def destroy(self):
        self.destroyed = True


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


class DesktopMenuTests(unittest.TestCase):
    def test_localization_and_env_precedence(self):
        en = desktop_menu.get_menu_labels("en")
        es = desktop_menu.get_menu_labels("es")
        pt = desktop_menu.get_menu_labels("pt")
        zh = desktop_menu.get_menu_labels("zh")
        self.assertEqual(en["menu_file"], "File")
        self.assertEqual(es["menu_file"], "Archivo")
        self.assertEqual(es["menu_view"], "Ver")
        self.assertEqual(es["paste"], "Pegar")
        self.assertEqual(es["back"], "Ir atrás")
        self.assertEqual(pt["menu_help"], "Ajuda")
        self.assertEqual(zh["menu_edit"], "编辑")
        self.assertEqual(desktop_menu.get_menu_labels("fr")["menu_file"], "File")

        with mock.patch.dict(os.environ, {"LANG_DEFAULT": "en", "DESKTOP_MENU_LANG": "es"}, clear=False):
            self.assertEqual(desktop_menu.get_menu_labels()["menu_help"], "Ayuda")

    def test_markdown_rendering_and_xss_neutralization(self):
        md = (
            "# Guía Rápida\n\n"
            "Texto con **negrita**, *cursiva*, ~~tachado~~ y `código <tag>`.\n\n"
            "- Uno\n- Dos\n\n"
            "1. Primero\n2. Segundo\n\n"
            "> Nota importante\n\n"
            "| Col1 | Col2 |\n| --- | --- |\n| A | B |\n\n"
            "```python\nprint('<hello>')\n```\n\n"
            "[Docs](https://seip25.github.io/Lila)\n"
            "[Local](/settings)\n"
            "[Bad](javascript:alert(1))\n"
            "[EncodedBad](java&#x09;script:alert(2))\n"
            "<script>alert('xss')</script>\n"
            "<img src=x onerror=alert(1)>\n"
        )
        rendered = desktop_menu.render_markdown(md)
        self.assertIn("<h1>Guía Rápida</h1>", rendered)
        self.assertIn("<strong>negrita</strong>", rendered)
        self.assertIn("<em>cursiva</em>", rendered)
        self.assertIn("<del>tachado</del>", rendered)
        self.assertIn("<code>código &lt;tag&gt;</code>", rendered)
        self.assertIn("<ul><li>Uno</li><li>Dos</li></ul>", rendered)
        self.assertIn("<ol><li>Primero</li><li>Segundo</li></ol>", rendered)
        self.assertIn("<blockquote><p>Nota importante</p></blockquote>", rendered)
        self.assertIn("<table><thead><tr><th>Col1</th><th>Col2</th></tr></thead>", rendered)
        self.assertIn('<pre><code class="language-python">print(&#x27;&lt;hello&gt;&#x27;)</code></pre>', rendered)
        self.assertIn('href="https://seip25.github.io/Lila"', rendered)
        self.assertIn('data-lila-external="1"', rendered)
        self.assertIn('<a href="/settings">Local</a>', rendered)
        self.assertNotIn("javascript:", rendered.lower().replace("javascript:alert", "SAFE_CHECK") if 'href="javascript' in rendered.lower() else "ok")
        self.assertNotIn('href="javascript:', rendered.lower())
        self.assertNotIn("java\tscript", rendered.lower())
        self.assertNotIn("<script>", rendered.lower())
        self.assertNotIn("<img", rendered.lower())

    def test_help_manual_dev_empty_save_and_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                empty = desktop_menu.read_help_manual()
                self.assertTrue(empty["is_empty"])
                self.assertEqual(empty["markdown"], "")
                self.assertEqual(empty["html"], "")
                self.assertTrue(empty["editable"])

                saved = desktop_menu.save_help_manual("# Mi Manual\n\nHola **mundo**")
                self.assertTrue(saved["ok"])
                self.assertFalse(saved["is_empty"])
                self.assertIn("<h1>Mi Manual</h1>", saved["html"])
                self.assertTrue((Path(tmp) / "resources" / "manual.md").is_file())

                with mock.patch.dict(os.environ, {"DESKTOP_HELP_EDITABLE": "False"}, clear=False):
                    ro = desktop_menu.save_help_manual("Otro contenido")
                    self.assertFalse(ro["ok"])
                    self.assertEqual(ro["reason"], "read-only")

                huge = "x" * (desktop_menu.MAX_MANUAL_BYTES + 10)
                too_big = desktop_menu.save_help_manual(huge)
                self.assertFalse(too_big["ok"])
            finally:
                os.chdir(old_cwd)

    def test_help_manual_frozen_override_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundled_root = Path(tmp) / "bundle"
            data_root = Path(tmp) / "appdata"
            (bundled_root / "resources").mkdir(parents=True, exist_ok=True)
            data_root.mkdir(parents=True, exist_ok=True)
            (bundled_root / "resources" / "manual.md").write_text("# Bundled", encoding="utf-8")

            def fake_base(*parts):
                return str(bundled_root.joinpath(*parts))

            def fake_data(*parts):
                return str(data_root.joinpath(*parts))

            with mock.patch.object(sys, "frozen", True, create=True), \
                 mock.patch.object(desktop_menu, "get_base_path", side_effect=fake_base), \
                 mock.patch.object(desktop_menu, "get_data_path", side_effect=fake_data):
                initial = desktop_menu.read_help_manual()
                self.assertEqual(initial["markdown"], "# Bundled")
                self.assertTrue(initial["has_bundled"])
                self.assertFalse(initial["has_override"])

                saved = desktop_menu.save_help_manual("# Custom User")
                self.assertTrue(saved["ok"])
                self.assertTrue(saved["has_override"])
                self.assertTrue(saved["has_bundled"])
                self.assertEqual(saved["markdown"], "# Custom User")
                self.assertTrue((data_root / "manual.md").is_file())

                reset = desktop_menu.reset_help_manual()
                self.assertTrue(reset["ok"])
                self.assertFalse(reset["has_override"])
                self.assertEqual(reset["markdown"], "# Bundled")
                self.assertFalse((data_root / "manual.md").exists())

    def test_build_menu_platforms_updates_and_hooks(self):
        fake_webview = types.ModuleType("webview")
        fake_menu_mod = types.ModuleType("webview.menu")
        fake_menu_mod.Menu = _FakeMenu
        fake_menu_mod.MenuAction = _FakeMenuAction
        fake_menu_mod.MenuSeparator = _FakeMenuSeparator
        fake_webview.menu = fake_menu_mod

        fake_app_pkg = types.ModuleType("app")
        fake_user_hook = types.ModuleType("app.desktop_menu")
        fake_user_hook.extra_menus = lambda wg, cfg: [_FakeMenu("Tools", [_FakeMenuAction("Custom", lambda: None)])]

        win = _FakeWindow()
        with mock.patch.dict(sys.modules, {"webview": fake_webview, "webview.menu": fake_menu_mod}), \
             mock.patch.dict(os.environ, {"DESKTOP_UPDATE_URL": "", "LILA_UPDATE_URL": ""}, clear=False):
            # Missing app.desktop_menu should work cleanly
            cfg_en = desktop_menu.DesktopMenuConfig.from_env(app_name="Demo", lang="en", update_url="")
            win_menus = desktop_menu.build_desktop_menu(lambda: win, cfg_en, platform_name="win32")
            self.assertEqual([m.title for m in win_menus], ["File", "Edit", "View", "Help"])
            help_titles = [getattr(i, "title", "---") for i in win_menus[3].items]
            self.assertIn("Manual / Help", help_titles)
            self.assertIn("About Demo", help_titles)
            self.assertNotIn("Check for Updates...", help_titles)

            # With update_url + macOS
            cfg_mac = desktop_menu.DesktopMenuConfig.from_env(
                app_name="Demo", lang="es", update_url="https://example.com/latest.json"
            )
            mac_menus = desktop_menu.build_desktop_menu(lambda: win, cfg_mac, platform_name="darwin")
            self.assertEqual([m.title for m in mac_menus], ["__app__", "Editar", "Ver", "Ayuda"])
            app_titles = [getattr(i, "title", "---") for i in mac_menus[0].items]
            self.assertIn("Acerca de Demo", app_titles)
            self.assertIn("Preferencias...", app_titles)
            self.assertIn("Salir", app_titles)
            ayuda_titles = [getattr(i, "title", "---") for i in mac_menus[3].items]
            self.assertIn("Buscar actualizaciones...", ayuda_titles)
            self.assertNotIn("Acerca de Demo", ayuda_titles)

            # Disabled
            cfg_off = desktop_menu.DesktopMenuConfig.from_env(enabled=False)
            self.assertEqual(desktop_menu.build_desktop_menu(lambda: win, cfg_off), [])

        # Custom app.desktop_menu hook
        with mock.patch.dict(
            sys.modules,
            {
                "webview": fake_webview,
                "webview.menu": fake_menu_mod,
                "app": fake_app_pkg,
                "app.desktop_menu": fake_user_hook,
            },
        ):
            menus_hooked = desktop_menu.build_desktop_menu(lambda: win, cfg_en, platform_name="linux")
            self.assertEqual(menus_hooked[-1].title, "Tools")

    def test_modal_dispatch_csp_safety_and_actions(self):
        cfg = desktop_menu.DesktopMenuConfig.from_env(app_name="MyApp", lang="es")

        # When CustomEvent is canceled by user listener, modal script does NOT run
        canceled_win = _FakeWindow(prevent_default=True)
        desktop_menu.open_about_modal(canceled_win, cfg)
        desktop_menu.open_preferences_modal(canceled_win, cfg)
        desktop_menu.open_help_modal(canceled_win, cfg)
        self.assertEqual(len(canceled_win.scripts), 3)
        self.assertTrue(all("CustomEvent(" in s for s in canceled_win.scripts))

        # When not canceled, built-in modal JS runs and has zero inline onclick handlers
        open_win = _FakeWindow(prevent_default=False, selected="hello world")
        desktop_menu.open_about_modal(open_win, cfg)
        desktop_menu.open_help_modal(open_win, cfg)
        desktop_menu.open_preferences_modal(open_win, cfg)
        modal_scripts = [s for s in open_win.scripts if "CustomEvent(" not in s or "__lilaDesktopModal" in s]
        self.assertGreaterEqual(len(modal_scripts), 3)
        for script in modal_scripts:
            self.assertNotIn("onclick=", script.lower())

        # Edit/View actions
        copied = []
        with mock.patch.object(desktop_menu, "set_clipboard_text", side_effect=lambda t: copied.append(t) or True), \
             mock.patch.object(desktop_menu, "get_clipboard_text", return_value="pasted"):
            desktop_menu.action_copy(lambda: open_win)
            desktop_menu.action_cut(lambda: open_win)
            desktop_menu.action_paste(lambda: open_win)
        self.assertEqual(copied, ["hello world", "hello world"])
        self.assertTrue(any('"pasted"' in s for s in open_win.scripts))

        desktop_menu.action_back(lambda: open_win)
        desktop_menu.action_forward(lambda: open_win)
        desktop_menu.action_reload(lambda: open_win)
        desktop_menu.action_zoom(lambda: open_win, 10)
        desktop_menu.action_fullscreen(lambda: open_win)
        desktop_menu.action_quit(lambda: open_win)
        self.assertEqual(open_win.fullscreen_toggles, 1)
        self.assertTrue(open_win.destroyed)

    def test_bridge_and_cli_flags(self):
        bridge = DesktopBridge()
        info = bridge.app_info()
        self.assertIn("lila_version", info)
        self.assertIn("description", info)
        self.assertIn("author", info)

        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                saved = bridge.save_help_manual("# Via Bridge")
                self.assertTrue(saved["ok"])
                loaded = bridge.get_help_manual()
                self.assertEqual(loaded["markdown"], "# Via Bridge")
            finally:
                os.chdir(old_cwd)

        runner = CliRunner()
        wide_env = {"COLUMNS": "200", "NO_COLOR": "1"}
        res_dev = runner.invoke(desktop_cli, ["dev", "--help"], env=wide_env)
        self.assertEqual(res_dev.exit_code, 0)
        self.assertIn("--menu", res_dev.output)
        self.assertIn("--no-menu", res_dev.output)
        self.assertIn("--help-file", res_dev.output)
        self.assertIn("--preferences-url", res_dev.output)
        self.assertIn("--about", res_dev.output)

        res_build = runner.invoke(desktop_cli, ["build", "--help"], env=wide_env)
        self.assertEqual(res_build.exit_code, 0)
        self.assertIn("--help-editable", res_build.output)
        self.assertIn("--no-help-editable", res_build.output)

        ConfigLoader.reload()


if __name__ == "__main__":
    unittest.main()
