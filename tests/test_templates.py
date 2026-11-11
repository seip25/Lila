import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from jinja2 import DictLoader, ChoiceLoader
from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.routing import Router
from lila.core import templates as tpl
from lila.core.templates import render, _wrap_page_source


# Extra in-memory templates for the tests (project templates come first).
tpl.jinja_env.loader.inner = ChoiceLoader([
    DictLoader({
        "t/page.jinja": "<h1>Hi {{ user }}</h1>{% block head %}<meta name=\"x-page\" content=\"1\">{% endblock %}{% include 't/card.jinja' %}",
        "t/card.jinja": "<div class=\"card\">card {{ user }}</div>",
        "t/legacy.jinja": "{% extends layout | default('lila/base.jinja') %}{% block title %}Legacy{% endblock %}{% block content %}<p>legacy</p>{% endblock %}",
    }),
    tpl.jinja_env.loader.inner,
])
tpl.jinja_env.cache.clear()

router = Router()


@router.get("/page")
async def page(request):
    return render(
        request,
        "t/page",
        {"user": "<Ana>"},
        title="Dashboard",
        description="Panel",
        jsonld={"@type": "WebPage", "name": "</script><b>"},
        scripts=["js/x.js"],
        styles=["https://cdn.example/x.css"],
        meta={"theme-color": "#fff", "og:locale": "es_AR"},
        canonical=True,
    )


@router.get("/legacy")
async def legacy(request):
    return render(request, "t/legacy")


@router.get("/raw")
async def raw(request):
    return render(request, "t/card", {"user": "B"}, layout=False)


client = TestClient(App(routes=[router], debug=False, rate_limit=None))


class TemplateTests(unittest.TestCase):
    def test_plain_page_is_wrapped_in_default_layout(self):
        html = client.get("/page").text
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("data-lila-outlet", html)
        self.assertIn("<h1>Hi &lt;Ana&gt;</h1>", html)
        # include is rendered as a fragment, never wrapped again
        self.assertEqual(html.count("<!DOCTYPE html>"), 1)
        self.assertIn('<div class="card">card &lt;Ana&gt;</div>', html)
        # page-level {% block head %} lands in <head>
        head = html.split("</head>")[0]
        self.assertIn('name="x-page"', head)

    def test_seo_head_from_render_kwargs(self):
        html = client.get("/page").text
        head = html.split("</head>")[0]
        self.assertIn("<title>Dashboard", head)
        self.assertIn('<meta name="description" content="Panel"', head)
        self.assertIn('property="og:locale" content="es_AR"', head)
        self.assertIn('name="theme-color" content="#fff"', head)
        self.assertIn('<link rel="canonical" href="http://testserver/page"', head)
        self.assertIn('<script src="/js/x.js" defer data-lila-head>', head)
        self.assertIn('href="https://cdn.example/x.css"', head)
        # JSON-LD cannot break out of its <script>
        self.assertIn("application/ld+json", head)
        self.assertNotIn("</script><b>", html)
        self.assertIn("\\u003c/script\\u003e", head)

    def test_legacy_extends_templates_still_work(self):
        html = client.get("/legacy").text
        self.assertIn("<title>Legacy</title>", html)
        self.assertIn("<p>legacy</p>", html)

    def test_layout_false_renders_fragment(self):
        self.assertEqual(client.get("/raw").text.strip(), '<div class="card">card B</div>')

    def test_wrap_preserves_line_numbers(self):
        src = "a\n{% block head %}\nx\n{% endblock %}\nb {{ c }}\n"
        wrapped = _wrap_page_source(src)
        self.assertTrue(wrapped.startswith("{% extends layout %}{% block content %}a\n"))
        content = wrapped.split("{% endblock %}")[0]
        self.assertEqual(content.count("\n"), src.count("\n"))

    def test_full_documents_are_not_wrapped(self):
        src = "<!DOCTYPE html><html><body>x</body></html>"
        self.assertEqual(_wrap_page_source(src), src)

    def test_404_uses_layout(self):
        res = client.get("/nope", headers={"accept": "text/html"})
        self.assertEqual(res.status_code, 404)
        self.assertIn("data-lila-outlet", res.text)
        self.assertIn('content="noindex"', res.text)


if __name__ == "__main__":
    unittest.main()
