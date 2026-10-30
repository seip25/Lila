import os
import shutil
import uuid
import unittest

from itsdangerous import BadSignature, URLSafeTimedSerializer


class SecretTests(unittest.TestCase):
    def test_empty_secret_is_never_used(self):
        from lila.core import config as config_module

        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_secret")
        work = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(work, exist_ok=True)
        old_cwd = os.getcwd()
        old_secret = os.environ.get("SECRET_KEY")
        try:
            os.chdir(work)
            os.environ["SECRET_KEY"] = ""
            config_module._SECRET_CACHE = None
            secret = config_module.get_secret_key()
            self.assertGreaterEqual(len(secret), 32)

            from lila.core.session import _get_session_serializer

            forged = URLSafeTimedSerializer("", salt="lila-session-salt").dumps(
                '{"user_id": 1, "email": "admin@example.com"}'
            )
            with self.assertRaises(BadSignature):
                _get_session_serializer().loads(forged)
        finally:
            os.chdir(old_cwd)
            if old_secret is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = old_secret
            config_module._SECRET_CACHE = None
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
