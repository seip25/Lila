import os
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.routing import Router
from lila.core.request import Request
from lila.core.csrf import CSRF


router = Router(prefix="/api")


@router.get("/typed")
async def typed(request: Request, page: int = 1, tags: list[int] = None):
    return {"page": page, "type": type(page).__name__, "tags": tags}


@router.get("/optional")
async def optional(request: Request, page: int | None = 1):
    return {"page": page, "type": type(page).__name__}


@router.get("/required")
async def required(request: Request, q: str):
    return {"q": q}


@router.get("/cached", cache=60)
async def cached(request: Request):
    return {"cookie": request.cookies.get("who", "none")}


@router.post("/form-csrf", csrf=True)
async def form_csrf(request: Request):
    form = await request.form()
    return {"ok": True, "keys": list(form.keys())}


app = App(routes=[router], debug=False, openapi=True, security=True, rate_limit=None)
client = TestClient(app, raise_server_exceptions=False)


class RoutingTests(unittest.TestCase):
    def test_typed_query_params(self):
        response = client.get("/api/typed?page=5")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page"], 5)
        self.assertEqual(response.json()["type"], "int")

    def test_optional_annotation(self):
        response = client.get("/api/optional?page=7")
        self.assertEqual(response.json()["page"], 7)
        self.assertEqual(response.json()["type"], "int")

    def test_list_query_params(self):
        response = client.get("/api/typed?tags=1&tags=2")
        self.assertEqual(response.json()["tags"], [1, 2])

    def test_invalid_int_is_422(self):
        response = client.get("/api/typed?page=abc")
        self.assertEqual(response.status_code, 422)

    def test_missing_required_is_422(self):
        response = client.get("/api/required")
        self.assertEqual(response.status_code, 422)

    def test_route_cache_is_per_identity(self):
        first = client.get("/api/cached", cookies={"who": "alice"})
        second = client.get("/api/cached", cookies={"who": "bob"})
        self.assertEqual(first.json(), {"cookie": "alice"})
        self.assertEqual(second.json(), {"cookie": "bob"})

    def test_csrf_accepts_html_form_body(self):
        token = "form-token"
        response = client.post(
            "/api/form-csrf",
            data={"_csrf": token, "name": "x"},
            cookies={"_csrf": CSRF.sign(token)},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_404_json_envelope(self):
        response = client.get("/api/nope", headers={"accept": "application/json"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])


if __name__ == "__main__":
    unittest.main()
