import unittest

from lila.core.admin import admin_routes, render_admin_menu
from lila.core.routing import Router


class AdminPrefixTests(unittest.TestCase):
    def test_custom_admin_prefix_routes_and_menu(self):
        router = Router()
        admin_routes(models=[], router=router, default_route="panel")
        paths = {route.path for route in router.get_routes()}
        self.assertIn("/panel/login", paths)
        self.assertIn("/panel", paths)
        self.assertNotIn("/admin/login", paths)

        menu = render_admin_menu([], prefix="/panel")
        self.assertIn("/panel/logout", menu)
        self.assertNotIn("/admin/logout", menu)


class AdminMenuActiveTests(unittest.TestCase):
    def _active(self, html):
        import re
        return re.findall(r'<a href="([^"]+)" class="[^"]*bg-blue-600[^"]*" aria-current="page">', html)

    def test_model_page_marks_only_its_link(self):
        class User:  # noqa: D401 - minimal stand-in
            pass

        class Product:
            pass

        class Req:
            class url:
                path = "/panel/users"

        html = render_admin_menu([User, Product], Req(), prefix="/panel")
        self.assertEqual(self._active(html), ["/panel/users"])
        self.assertNotIn('id="admin-sidebar"', html)  # wrapper lives in the template

    def test_dashboard_active_only_on_its_path(self):
        class Req:
            class url:
                path = "/panel"

        self.assertEqual(self._active(render_admin_menu([], Req(), prefix="/panel")), ["/panel"])


if __name__ == "__main__":
    unittest.main()
