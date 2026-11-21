import unittest

from lila.cli.scaffold_crud import generate_api_route_file, generate_react_page, generate_web_route_file

COLUMNS = ["id", "name", "price", "published", "password", "internal_note", "active", "created_at"]
TYPES = {"id": int, "name": str, "price": float, "published": bool, "password": str, "internal_note": str,
         "active": int, "created_at": str}


class CrudScaffoldTests(unittest.TestCase):
    def test_api_is_valid_safe_and_paginated(self):
        source = generate_api_route_file("Product", "product", "products", COLUMNS, TYPES,
                                         private={"internal_note"}, auth=True)
        compile(source, "product.py", "exec")
        self.assertNotIn("str(e", source)  # never leak database errors
        self.assertIn("paginate_async(", source)
        self.assertIn('"/product/{id:int}"', source)
        self.assertEqual(source.count("auth=True"), 5)
        for secret in ("internal_note", "password"):
            self.assertNotIn(secret, source.split("SORTABLE")[1].split("\n")[0])
            self.assertNotIn(f"    {secret}:", source)

    def test_web_routes(self):
        react = generate_web_route_file("Product", "product", react=True, auth=True)
        compile(react, "w.py", "exec")
        self.assertIn('react_render(', react)
        self.assertIn('"Crud/Product"', react)
        jinja = generate_web_route_file("Product", "product")
        compile(jinja, "w.py", "exec")
        self.assertIn('render(request, "product/index"', jinja)
        self.assertNotIn("auth=True", jinja)

    def test_react_page(self):
        page = generate_react_page("Product", "product", COLUMNS, TYPES, {"password", "internal_note"})
        self.assertIn("export default function ProductCrud", page)
        self.assertIn('<Input name="price" type="number"', page)
        self.assertIn('<Checkbox name="published"', page)
        self.assertIn("onDelete={`${api}/:id`}", page)
        for hidden in ("password", "internal_note", '"active"'):
            self.assertNotIn(hidden, page)


if __name__ == "__main__":
    unittest.main()
