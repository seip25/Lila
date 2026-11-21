import json
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.react import react_render, compile_meta, resolve_spa_meta
from lila.core.routing import Router
from lila.core.vite import ViteBridge, ViteManifestMissing
from lila.testing import override_env

MANIFEST = {
    "resources/react/main.jsx": {
        "file": "assets/main-abc.js",
        "isEntry": True,
        "imports": ["_vendor-1.js"],
        "css": ["assets/main-abc.css"],
    },
    "_vendor-1.js": {"file": "assets/vendor-1.js", "css": ["assets/vendor.css"]},
    "resources/react/spa.jsx": {"file": "assets/spa-1.js", "isEntry": True, "imports": ["_vendor-1.js"]},
}


class ProjectDir(unittest.TestCase):
    """Runs each test inside a throwaway project directory."""

    manifest = MANIFEST

    def setUp(self):
        self.cwd = os.getcwd()
        self.dir = tempfile.mkdtemp(prefix="lila-react-")
        os.chdir(self.dir)
        os.makedirs(os.path.join("public", "build", ".vite"))
        if self.manifest is not None:
            with open(os.path.join("public", "build", ".vite", "manifest.json"), "w") as fh:
                json.dump(self.manifest, fh)
        ViteBridge.reset()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)
        ViteBridge.reset()


class ViteBridgeTests(ProjectDir):
    def test_build_tags_follow_imports(self):
        with override_env(DEBUG="False"):
            tags = ViteBridge.tags("resources/react/main.jsx")
        self.assertIn('<script type="module" src="/public/build/assets/main-abc.js"></script>', tags)
        self.assertIn('<link rel="modulepreload" href="/public/build/assets/vendor-1.js" />', tags)
        self.assertIn('href="/public/build/assets/main-abc.css"', tags)
        self.assertIn('href="/public/build/assets/vendor.css"', tags)
        self.assertEqual(len(ViteBridge.version()), 12)

    def test_unknown_entry_raises(self):
        with override_env(DEBUG="False"):
            with self.assertRaises(ViteManifestMissing):
                ViteBridge.tags("resources/react/missing.jsx")

    def test_hot_file_only_in_debug(self):
        with open(os.path.join("public", "build", "hot"), "w") as fh:
            fh.write("http://127.0.0.1:5173")
        with override_env(DEBUG="True"):
            tags = ViteBridge.tags("resources/react/main.jsx")
            self.assertIn("http://127.0.0.1:5173/@vite/client", tags)
            self.assertIn("@react-refresh", tags)
        with override_env(DEBUG="False"):
            # A stale hot file in production never points pages at Vite.
            self.assertNotIn("5173", ViteBridge.tags("resources/react/main.jsx"))


router = Router()


@router.get("/r")
async def react_page(request):
    return react_render(
        request, "Users/Show", {"name": "</script><b>x"},
        title="Profile", description="User page",
        jsonld={"@context": "https://schema.org", "@type": "Person", "name": "Ana"},
        meta={"theme-color": "#fff"},
    )


@router.get("/web-only", desktop=False)
async def web_only(request):
    return {"ok": True}


@router.get("/desk", desktop="only")
async def desktop_only(request):
    return {"ok": True}


router.spa("/app", meta={
    "*": {"title": "App", "description": "SPA"},
    "users/:id": lambda request, params: {"title": f"User {params['id']}", "props": {"id": params["id"]}},
    "docs/*": {"title": "Docs", "robots": "noindex"},
})

api = Router(prefix="/api")


@api.get("/ping")
async def ping(request):
    return {"pong": True}


billing = Router(prefix="/billing", desktop=False)


@billing.get("/plans")
async def plans(request):
    return {"plans": []}


class ReactRenderTests(ProjectDir):
    def client(self, **env):
        with override_env(DEBUG="False", **env):
            app = App(routes=[router, billing], rate_limit=None, debug=False)
            app.include_router(api)  # included after the SPA catch-all
        return TestClient(app)

    def test_shell_has_seo_and_escaped_props(self):
        with override_env(DEBUG="False"):
            res = self.client().get("/r")
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn("<title>Profile", body)
        self.assertIn('<meta name="description" content="User page"', body)
        self.assertIn('application/ld+json', body)
        self.assertIn('<meta name="theme-color" content="#fff"', body)
        self.assertIn('/public/build/assets/main-abc.js', body)
        self.assertNotIn("</script><b>", body)
        self.assertNotIn("tailwind.js", body)
        self.assertIn("_csrf", res.headers.get("set-cookie", ""))
        payload = body.split('id="lila-page">', 1)[1].split("</script>", 1)[0]
        page = json.loads(payload)
        self.assertEqual(page["component"], "Users/Show")
        self.assertEqual(page["props"]["name"], "</script><b>x")
        self.assertFalse(page["desktop"])
        self.assertEqual(page["head"]["jsonld"][0]["@type"], "Person")

    def test_json_navigation_and_version_mismatch(self):
        with override_env(DEBUG="False"):
            client = self.client()
            res = client.get("/r", headers={"X-Lila-React": "1"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["component"], "Users/Show")
            self.assertTrue(data["head"]["title"].startswith("Profile"))
            stale = client.get("/r", headers={"X-Lila-React": "1", "X-Lila-Version": "old"})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(stale.headers["x-lila-location"], "/r")

    def test_missing_build_is_a_clear_500(self):
        os.remove(os.path.join("public", "build", ".vite", "manifest.json"))
        ViteBridge.reset()
        with override_env(DEBUG="False"):
            res = self.client().get("/r")
        self.assertEqual(res.status_code, 500)

    def test_spa_meta_and_catch_all_order(self):
        with override_env(DEBUG="False"):
            client = self.client()
            home = client.get("/app")
            self.assertIn("<title>App", home.text)
            self.assertIn("/public/build/assets/spa-1.js", home.text)
            user = client.get("/app/users/42")
            self.assertIn("<title>User 42", user.text)
            head = client.get("/app/docs/a/b", headers={"X-Lila-Head": "1"}).json()
            self.assertEqual(head["head"]["robots"], "noindex")
            self.assertTrue(head["head"]["title"].startswith("Docs"))
            self.assertEqual(client.get("/app/logo.png").status_code, 404)
            # Routes included after router.spa() still win over the catch-all.
            self.assertEqual(client.get("/api/ping").json(), {"pong": True})

    def test_web_mode_drops_desktop_only_routes(self):
        with override_env(DEBUG="False"):
            client = self.client()
            self.assertEqual(client.get("/web-only").status_code, 200)
            self.assertEqual(client.get("/billing/plans").status_code, 200)
            self.assertEqual(client.get("/desk").status_code, 404)

    def test_desktop_mode_drops_web_only_routes(self):
        with override_env(DEBUG="False", LILA_DESKTOP="1", LILA_DESKTOP_EXCLUDE="/api/ping"):
            client = self.client()
            self.assertEqual(client.get("/web-only").status_code, 404)
            self.assertEqual(client.get("/billing/plans").status_code, 404)
            self.assertEqual(client.get("/desk").status_code, 200)
            self.assertEqual(client.get("/api/ping").status_code, 404)
            self.assertEqual(client.get("/js/lila-client.js").status_code, 200)
            paths = client.get("/openapi.json").json()["paths"]
            self.assertNotIn("/web-only", paths)
            self.assertNotIn("/billing/plans", paths)
            page = client.get("/r", headers={"X-Lila-React": "1"}).json()
            self.assertTrue(page["desktop"])
            self.assertTrue(any("web" in pattern for pattern in page["unavailable"]))


class SpaMetaTests(unittest.TestCase):
    def test_static_beats_param_and_wildcard(self):
        import asyncio

        default, routes = compile_meta({
            "*": {"title": "Base", "meta": {"a": "1"}},
            "users/new": {"title": "New"},
            "users/:id": {"title": "Show"},
            "users/*": {"title": "Any"},
        })
        resolve = lambda path: asyncio.run(resolve_spa_meta(None, path, default, routes))
        self.assertEqual(resolve("users/new")["title"], "New")
        self.assertEqual(resolve("users/7")["title"], "Show")
        self.assertEqual(resolve("users/7/edit")["title"], "Any")
        self.assertEqual(resolve("other")["title"], "Base")


class DesktopPatternTests(unittest.TestCase):
    def test_patterns(self):
        from lila.core.desktop import match_pattern

        self.assertTrue(match_pattern("/payments", "/payments"))
        self.assertTrue(match_pattern("/payments", "/payments/{id:int}"))
        self.assertFalse(match_pattern("/payments", "/payments-info"))
        self.assertTrue(match_pattern("/api/*/upload", "/api/v1/upload"))
        self.assertTrue(match_pattern("name:stripe_*", "/x", "stripe_webhook"))
        self.assertFalse(match_pattern("/", "/anything"))

    def test_suggestions(self):
        from starlette.routing import Route
        from lila.core.desktop import suggest_exclusions

        async def h(request):
            return None

        routes = [Route("/checkout", h), Route("/api/upload", h), Route("/dashboard", h), Route("/js/x.js", h)]
        found = [path for path, _ in suggest_exclusions(routes)]
        self.assertEqual(found, ["/checkout", "/api/upload"])


class StaticDirsTests(ProjectDir):
    def test_public_subdirectories_are_served_at_root(self):
        os.makedirs(os.path.join("public", "css"))
        with open(os.path.join("public", "css", "lila.css"), "w") as fh:
            fh.write("a{}")
        with override_env(DEBUG="False"):
            client = TestClient(App(routes=[], rate_limit=None, debug=False))
            self.assertEqual(client.get("/css/lila.css").status_code, 200)
            self.assertEqual(client.get("/build/.vite/manifest.json").status_code, 200)


if __name__ == "__main__":
    unittest.main()
