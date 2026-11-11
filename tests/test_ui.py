import os
import unittest
from enum import Enum
from typing import Literal, Optional

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from jinja2 import ChoiceLoader, DictLoader
from pydantic import BaseModel, EmailStr, Field
from starlette.testclient import TestClient

from lila.core import templates as tpl
from lila.core.app import App
from lila.core.routing import Router
from lila.core.templates import render
from lila.core.ui import UI, field_widget, render_form, render_pagination


class Role(Enum):
    ADMIN = "admin"
    USER = "user"


class Signup(BaseModel):
    name: str = Field(min_length=2, max_length=50, title="Full name")
    email: EmailStr
    age: Optional[int] = Field(default=None, ge=18, le=120)
    password: str = Field(min_length=8)
    password_2: str = Field(json_schema_extra={"ui": {"match": "password", "label": "Repeat"}})
    plan: Literal["free", "pro"] = "free"
    role: Role = Role.USER
    bio: Optional[str] = Field(default=None, json_schema_extra={"ui": {"widget": "textarea"}})
    terms: bool = False


class FormTests(unittest.TestCase):
    def setUp(self):
        self.html = str(render_form(Signup, action="/api/signup", snackbar=True, redirect="/ok",
                                    errors={"email": "Already used <x>"}))

    def test_html5_attributes_mirror_pydantic(self):
        h = self.html
        self.assertIn('name="name" type="text" required', h)
        self.assertIn('minlength="2" maxlength="50"', h)
        self.assertIn('name="email" type="email" required', h)
        self.assertIn('name="age" type="number"', h)
        self.assertIn('min="18" max="120"', h)
        self.assertIn('name="password" type="password" required class="input-lila w-full" minlength="8"', h)
        self.assertIn('data-match="password"', h)
        self.assertIn('<textarea id="f-bio" name="bio"', h)
        self.assertIn('type="checkbox" id="f-terms" name="terms" value="1" data-unchecked="0"', h)
        self.assertIn('<option value="user" selected>User</option>', h)
        self.assertIn('<option value="free" selected>free</option>', h)
        self.assertNotIn('<option value="">—</option><option value="free"', h)   # not optional
        self.assertIn(">Full name<", h)

    def test_form_attributes_and_escaped_errors(self):
        h = self.html
        self.assertIn('action="/api/signup" method="post" data-lila-form data-snackbar data-redirect="/ok"', h)
        self.assertIn('data-error-for="email">Already used &lt;x&gt;</p>', h)
        self.assertIn('aria-invalid="true"', h)

    def test_widget_for_optional_select(self):
        class M(BaseModel):
            color: Optional[Literal["red", "blue"]] = None

        w = field_widget("color", M.model_fields["color"])
        self.assertEqual(w["control"], "select")
        self.assertTrue(w["optional"])


class PaginationAndUiTests(unittest.TestCase):
    def test_pagination_keeps_query(self):
        class Req:
            query_params = {"q": "café", "page": "2"}

            class url:
                path = "/products"

        html = str(render_pagination({"page": 2, "pages": 3}, Req()))
        self.assertIn('href="/products?q=caf%C3%A9&amp;page=3"', html)
        self.assertIn('aria-current="page">2<', html)
        self.assertEqual(str(render_pagination({"page": 1, "pages": 1})), "")

    def test_components_escape_and_translate(self):
        ui = UI({"save": "Guardar"})
        self.assertIn(">Guardar</button>", str(ui.button("save", type="submit")))
        self.assertIn("&lt;b&gt;", str(ui.alert("<b>", type="error", dismissible=True)))
        self.assertIn('data-close-modal', str(ui.modal("m1", "Title", "Body")))
        self.assertIn('data-match="pwd"', str(ui.input("pwd2", "Repeat", type="password", data_match="pwd")))


tpl.jinja_env.loader.inner = ChoiceLoader([
    DictLoader({"t_ui/page.jinja": "{{ form(Signup, action='/api/s', submit='save') }}{{ ui.badge('save', color='green') }}{{ pagination(page) }}"}),
    tpl.jinja_env.loader.inner,
])
tpl.jinja_env.cache.clear()
router = Router()


@router.get("/ui")
async def ui_page(request):
    return render(request, "t_ui/page", {"Signup": Signup, "page": {"page": 1, "pages": 2}}, lang_default="es")


class TemplateIntegrationTests(unittest.TestCase):
    def test_helpers_inside_templates(self):
        html = TestClient(App(routes=[router], debug=False, rate_limit=None)).get("/ui").text
        self.assertIn('name="_csrf"', html)                  # csrf_input injected
        self.assertIn('data-lila-form', html)
        self.assertIn('href="/ui?page=2"', html)


if __name__ == "__main__":
    unittest.main()
