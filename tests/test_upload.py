import io
import os
import shutil
import unittest
import uuid


class UploadTests(unittest.TestCase):
    def test_default_upload_is_served(self):
        from starlette.testclient import TestClient
        from lila.core.app import App
        from lila.core.routing import Router
        from lila.core.request import Request
        from lila.core.files import upload

        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp_upload")
        work = os.path.join(root, uuid.uuid4().hex)
        os.makedirs(work, exist_ok=True)
        old_cwd = os.getcwd()
        old_secret = os.environ.get("SECRET_KEY")
        try:
            os.chdir(work)
            os.environ["SECRET_KEY"] = "0123456789abcdef0123456789abcdef"
            router = Router()

            @router.post("/upload")
            async def up(request: Request):
                return await upload(request)

            app = App(routes=[router], debug=False, openapi=False)
            client = TestClient(app)
            response = client.post(
                "/upload",
                files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["url"].startswith("/uploads/"))
            self.assertNotIn("path", payload)
            self.assertEqual(client.get(payload["url"]).status_code, 200)
        finally:
            os.chdir(old_cwd)
            if old_secret is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = old_secret
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
