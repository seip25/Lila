import asyncio
import unittest

from lila.core.session import Session, _get_session_serializer


class FakeResponse:
    def __init__(self):
        self.cookies = {}

    def set_cookie(self, **kwargs):
        self.cookies[kwargs["key"]] = kwargs["value"]

    def delete_cookie(self, **kwargs):
        self.cookies.pop(kwargs.get("key", "session"), None)


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_password_is_not_written_to_the_cookie(self):
        response = FakeResponse()
        payload = {"user_id": 1, "email": "a@b.c", "password": "$argon2id$secret", "name": "A"}
        ok = await Session.set_async(payload, response)
        self.assertTrue(ok)
        raw = response.cookies["session"]
        decoded = _get_session_serializer().loads(raw)
        self.assertIn("user_id", decoded)
        self.assertNotIn("argon2", decoded)

    async def test_large_session_uses_server_store(self):
        response = FakeResponse()
        payload = {"user_id": 1, "blob": "x" * 5000}
        ok = await Session.set_async(payload, response)
        self.assertTrue(ok)
        raw = response.cookies["session"]
        decoded = _get_session_serializer().loads(raw)
        self.assertTrue(str(decoded).startswith("sid:"))


if __name__ == "__main__":
    unittest.main()
