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


if __name__ == "__main__":
    unittest.main()
