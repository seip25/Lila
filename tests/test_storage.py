import io
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789")

from starlette.testclient import TestClient

from lila.core import storage as storage_mod
from lila.core.app import App
from lila.core.files import upload
from lila.core.request import Request
from lila.core.routing import Router
from lila.core.storage import LocalStorage, S3Storage, clean_key, set_storage
from lila.testing import override_env


class FakeS3:
    def __init__(self):
        self.objects = {}

    def upload_file(self, path, bucket, key, ExtraArgs=None):  # noqa: N803 - boto3 names
        with open(path, "rb") as fh:
            self.objects[(bucket, key)] = (fh.read(), (ExtraArgs or {}).get("ContentType"))

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self.objects[(Bucket, Key)] = (Body, ContentType)

    def generate_presigned_url(self, op, Params, ExpiresIn):  # noqa: N803
        return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?X-Amz-Expires={ExpiresIn}"

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.objects.pop((Bucket, Key), None)

    def head_object(self, Bucket, Key):  # noqa: N803
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)


router = Router()


@router.post("/up")
async def up(request: Request):
    return await upload(request, folder="avatars/../../etc")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp()
        os.chdir(self.tmp)
        os.makedirs("public")
        storage_mod._STORAGE.clear()

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)
        storage_mod._STORAGE.clear()

    def test_clean_key(self):
        self.assertEqual(clean_key("../../etc/passwd"), "etc/passwd")
        self.assertEqual(clean_key("/a//b/./c d.txt"), "a/b/c_d.txt")

    def test_upload_to_s3_with_presigned_and_public_urls(self):
        fake = FakeS3()
        set_storage(S3Storage(bucket="media", client=fake, prefix="uploads/", public_url=""), "s3")
        with override_env(STORAGE_DRIVER="s3"):
            client = TestClient(App(routes=[router], rate_limit=None, debug=False))
            res = client.post("/up", files={"file": ("photo.png", io.BytesIO(b"PNGDATA"), "image/png")}).json()
        self.assertTrue(res["success"])
        self.assertTrue(res["key"].startswith("avatars/etc/photo_"))
        stored_key = f"uploads/{res['key']}"
        self.assertEqual(fake.objects[("media", stored_key)], (b"PNGDATA", "image/png"))
        self.assertIn("X-Amz-Expires=3600", res["url"])
        self.assertEqual(os.listdir(os.path.join("public", "uploads")), [])  # nothing left on disk

        cdn = S3Storage(bucket="media", client=fake, prefix="", public_url="https://cdn.example/")
        self.assertEqual(cdn.url("a/b.png"), "https://cdn.example/a/b.png")
        self.assertTrue(cdn.exists("../" + stored_key))
        cdn.delete(stored_key)
        self.assertFalse(cdn.exists(stored_key))

    def test_local_folder_is_served(self):
        with override_env(STORAGE_DRIVER="local"):
            client = TestClient(App(routes=[router], rate_limit=None, debug=False))
            res = client.post("/up", files={"file": ("n.txt", io.BytesIO(b"hello"), "text/plain")}).json()
            self.assertTrue(res["url"].startswith("/uploads/avatars/etc/n_"))
            self.assertEqual(client.get(res["url"]).text, "hello")
        local = LocalStorage(root=os.path.join(self.tmp, "public", "uploads"))
        self.assertEqual(local.put_bytes(b"x", "r/1.csv"), "/uploads/r/1.csv")
        self.assertTrue(local.exists("r/1.csv"))
        self.assertTrue(local.delete("r/1.csv"))


if __name__ == "__main__":
    unittest.main()
