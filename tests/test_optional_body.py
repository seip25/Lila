import unittest

from pydantic import BaseModel
from starlette.testclient import TestClient

from lila.core.app import App
from lila.core.request import Request
from lila.core.routing import Router


class Payload(BaseModel):
    name: str


class Filters(BaseModel):
    q: str


class OptionalBodyTests(unittest.TestCase):
    def test_optional_body_can_be_absent(self):
        router = Router()

        @router.post("/optional")
        async def optional(request: Request, data: Payload | None = None):
            return {"data": data.model_dump() if data else None}

        @router.post("/required")
        async def required(request: Request, data: Payload):
            return {"data": data.model_dump()}

        @router.get("/filters")
        async def filters(request: Request, filters: Filters | None = None):
            return {"q": filters.q if filters else None}

        client = TestClient(App(routes=[router], debug=False, openapi=False))
        self.assertEqual(client.post("/optional").status_code, 200)
        self.assertIsNone(client.post("/optional").json()["data"])
        self.assertEqual(client.post("/required").status_code, 422)
        self.assertEqual(client.post("/optional", json={"name": "x"}).json()["data"]["name"], "x")
        self.assertEqual(client.get("/filters").status_code, 200)
        self.assertIsNone(client.get("/filters").json()["q"])
        self.assertEqual(client.get("/filters", params={"q": "abc"}).json()["q"], "abc")


if __name__ == "__main__":
    unittest.main()
