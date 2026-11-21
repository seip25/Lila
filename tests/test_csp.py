import os
import re
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.csp import PLACEHOLDER, CSPConfig, nonce_attr
from lila.core.responses import HTMLResponse
from lila.core.routing import Router
from lila.core.templates import render

router = Router()


@router.get("/page")
async def page(request):
    return HTMLResponse(f"<html><head><script{nonce_attr(request)}>1</script></head><body>ok</body></html>")


@router.get("/cached", cache=60, cache_public=True)
async def cached(request):
    return f"<script{nonce_attr(request)}>2</script>"


@router.get("/json")
async def data(request):
    return {"ok": True}


@router.get("/jinja")
async def jinja_page(request):
    return render(request, "index", title="Home")


def nonce_of(response):
    header = response.headers.get("content-security-policy") or response.headers.get("content-security-policy-report-only")
    match = re.search(r"'nonce-([^']+)'", header or "")
    return match.group(1) if match else None


class CSPTests(unittest.TestCase):
    def client(self, csp=True):
        return TestClient(App(routes=[router], rate_limit=None, debug=False, csp=csp))

    def test_html_gets_policy_and_matching_nonce(self):
        res = self.client().get("/page", headers={"accept": "text/html"})
        nonce = nonce_of(res)
        self.assertTrue(nonce and len(nonce) == len(PLACEHOLDER))
        self.assertIn(f'<script nonce="{nonce}">', res.text)
        self.assertNotIn(PLACEHOLDER, res.text)
        policy = res.headers["content-security-policy"]
        for part in ("'strict-dynamic'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"):
            self.assertIn(part, policy)
        self.assertNotIn("etag", res.headers)
        self.assertEqual(int(res.headers["content-length"]), len(res.content))

    def test_nonce_changes_per_request_even_for_cached_routes(self):
        client = self.client()
        first = client.get("/cached")
        second = client.get("/cached")
        self.assertNotEqual(nonce_of(first), nonce_of(second))
        self.assertIn(f'nonce="{nonce_of(second)}"', second.text)

    def test_json_is_untouched(self):
        res = self.client().get("/json")
        self.assertNotIn("content-security-policy", res.headers)
        self.assertIn("etag", res.headers)

    def test_disabled_by_default(self):
        res = self.client(csp=False).get("/page")
        self.assertNotIn("content-security-policy", res.headers)
        self.assertIn("<script>1</script>", res.text)

    def test_report_only_and_custom_sources(self):
        res = self.client("report-only").get("/page")
        self.assertIn("content-security-policy-report-only", res.headers)
        config = CSPConfig({"img-src": ["https://cdn.example"], "script-src!": ["'self'"], "report-uri": "/csp"})
        policy = config.build("abc")
        self.assertIn("img-src 'self' data: blob: https: https://cdn.example", policy)
        self.assertIn("script-src 'nonce-abc' 'self';", policy)
        self.assertTrue(policy.endswith("report-uri /csp"))

    def test_jinja_layout_scripts_carry_the_nonce(self):
        res = self.client().get("/jinja", headers={"accept": "text/html"})
        nonce = nonce_of(res)
        scripts = re.findall(r"<script\b[^>]*>", res.text)
        executable = [s for s in scripts if "application/ld+json" not in s and "application/json" not in s]
        self.assertTrue(executable)
        for tag in executable:
            self.assertIn(f'nonce="{nonce}"', tag)

    def test_swagger_page(self):
        res = self.client().get("/docs", headers={"accept": "text/html"})
        self.assertEqual(res.text.count(f'nonce="{nonce_of(res)}"'), 3)


class TemplatesHaveNoInlineHandlers(unittest.TestCase):
    def test_framework_templates_are_csp_clean(self):
        root = os.path.join(os.path.dirname(__file__), "..", "lila")
        offenders = []
        for folder in ("resources/html", "cli"):
            for dirpath, _dirs, files in os.walk(os.path.join(root, folder)):
                for name in files:
                    if not name.endswith((".jinja", ".py", ".html")):
                        continue
                    with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                        text = fh.read()
                    if re.search(r'\son(click|change|submit|input|load)="', text):
                        offenders.append(name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
