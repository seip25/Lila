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
        max_age, decoded = _get_session_serializer().loads(raw)
        self.assertEqual(max_age, 86400)
        self.assertIn("user_id", decoded)
        self.assertNotIn("argon2", decoded)

    async def test_large_session_uses_server_store(self):
        response = FakeResponse()
        payload = {"user_id": 1, "blob": "x" * 5000}
        ok = await Session.set_async(payload, response)
        self.assertTrue(ok)
        raw = response.cookies["session"]
        _, decoded = _get_session_serializer().loads(raw)
        self.assertTrue(str(decoded).startswith("sid:"))

    async def test_get_honours_max_age_used_in_set(self):
        import time
        from unittest import mock

        response = FakeResponse()
        await Session.set_async({"user_id": 7}, response, max_age=30 * 86400)

        class Req:
            cookies = {"session": response.cookies["session"]}

        # Two days later: older code rejected it with the 1-day default.
        future = time.time() + 2 * 86400
        with mock.patch("time.time", return_value=future):
            self.assertEqual(await Session.get_async(Req()), {"user_id": 7})
            # An explicit shorter max_age still wins.
            self.assertIsNone(await Session.get_async(Req(), max_age=3600))

    async def test_legacy_cookie_still_readable(self):
        legacy = _get_session_serializer().dumps('{"user_id": 3}')

        class Req:
            cookies = {"session": legacy}

        self.assertEqual(await Session.get_async(Req()), {"user_id": 3})


if __name__ == "__main__":
    unittest.main()
