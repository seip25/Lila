"""File storage drivers for uploads: local disk or S3-compatible buckets.

``.env``::

    STORAGE_DRIVER=local            # default: public/uploads served at /uploads
    STORAGE_DRIVER=s3               # AWS S3, Cloudflare R2, MinIO, DigitalOcean Spaces...
    S3_BUCKET=my-bucket
    S3_REGION=us-east-1
    S3_ENDPOINT_URL=                # R2/MinIO/Spaces endpoint (empty for AWS)
    S3_ACCESS_KEY_ID=...
    S3_SECRET_ACCESS_KEY=...
    S3_PREFIX=uploads/              # key prefix inside the bucket
    S3_PUBLIC_URL=                  # CDN/public base URL; empty = private bucket + presigned URLs
    S3_PRESIGN_SECONDS=3600

``pip install "lila-framework[s3]"`` installs boto3. ``upload()`` uses the
configured driver automatically; code can also call it directly::

    from lila.core.storage import storage
    url = await storage().put_bytes_async(b"...", "reports/2026.csv", "text/csv")
    link = await storage().url_async("reports/2026.csv")      # presigned when private
    await storage().delete_async("reports/2026.csv")
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from typing import Any, Optional

from lila.core.config import ENV_CONFIG, get_base_path

_SAFE_KEY = re.compile(r"[^A-Za-z0-9._/\-]")


def clean_key(key: str) -> str:
    """Bucket key without traversal, absolute paths or odd characters."""
    parts = [p for p in str(key or "").replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return _SAFE_KEY.sub("_", "/".join(parts))


class LocalStorage:
    """public/uploads (served by App at /uploads)."""

    driver = "local"

    def __init__(self, root: Optional[str] = None, base_url: str = "/uploads"):
        self.root = root or get_base_path("public", "uploads")
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> str:
        path = os.path.realpath(os.path.join(self.root, clean_key(key)))
        if not path.startswith(os.path.realpath(self.root) + os.sep):
            raise ValueError("invalid storage key")
        return path

    def put_file(self, local_path: str, key: str, content_type: Optional[str] = None) -> str:
        target = self._path(key)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.realpath(local_path) != target:
            shutil.move(local_path, target)
        return self.url(key)

    def put_bytes(self, data: bytes, key: str, content_type: Optional[str] = None) -> str:
        target = self._path(key)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(data)
        return self.url(key)

    def url(self, key: str, expires: Optional[int] = None) -> str:
        return f"{self.base_url}/{clean_key(key)}"

    def delete(self, key: str) -> bool:
        try:
            os.remove(self._path(key))
            return True
        except FileNotFoundError:
            return False

    def exists(self, key: str) -> bool:
        return os.path.isfile(self._path(key))

    # async wrappers
    async def put_file_async(self, local_path: str, key: str, content_type: Optional[str] = None) -> str:
        return await asyncio.to_thread(self.put_file, local_path, key, content_type)

    async def put_bytes_async(self, data: bytes, key: str, content_type: Optional[str] = None) -> str:
        return await asyncio.to_thread(self.put_bytes, data, key, content_type)

    async def url_async(self, key: str, expires: Optional[int] = None) -> str:
        return self.url(key, expires)

    async def delete_async(self, key: str) -> bool:
        return await asyncio.to_thread(self.delete, key)


class S3Storage(LocalStorage):
    """S3-compatible bucket via boto3 (uploads are multipart for big files)."""

    driver = "s3"

    def __init__(self, bucket: Optional[str] = None, client: Any = None, prefix: Optional[str] = None,
                 public_url: Optional[str] = None, presign_seconds: Optional[int] = None):
        get = ENV_CONFIG.get
        self.bucket = bucket or str(get("S3_BUCKET", "") or "")
        if not self.bucket:
            raise RuntimeError("STORAGE_DRIVER=s3 needs S3_BUCKET")
        self.prefix = clean_key(prefix if prefix is not None else str(get("S3_PREFIX", "uploads/") or ""))
        if self.prefix:
            self.prefix += "/"
        self.public_url = (public_url if public_url is not None else str(get("S3_PUBLIC_URL", "") or "")).rstrip("/")
        self.presign_seconds = int(presign_seconds or get("S3_PRESIGN_SECONDS", 3600) or 3600)
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3  # type: ignore
            except ImportError as exc:  # pragma: no cover - depends on the extra
                raise RuntimeError('STORAGE_DRIVER=s3 needs boto3: pip install "lila-framework[s3]"') from exc
            get = ENV_CONFIG.get
            self._client = boto3.client(
                "s3",
                region_name=str(get("S3_REGION", "") or "") or None,
                endpoint_url=str(get("S3_ENDPOINT_URL", "") or "") or None,
                aws_access_key_id=str(get("S3_ACCESS_KEY_ID", "") or "") or None,
                aws_secret_access_key=str(get("S3_SECRET_ACCESS_KEY", "") or "") or None,
            )
        return self._client

    def _key(self, key: str) -> str:
        return f"{self.prefix}{clean_key(key)}"

    def put_file(self, local_path: str, key: str, content_type: Optional[str] = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self.client.upload_file(local_path, self.bucket, self._key(key), ExtraArgs=extra or None)
        try:
            os.remove(local_path)
        except OSError:
            pass
        return self.url(key)

    def put_bytes(self, data: bytes, key: str, content_type: Optional[str] = None) -> str:
        kwargs = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data, **kwargs)
        return self.url(key)

    def url(self, key: str, expires: Optional[int] = None) -> str:
        if self.public_url:
            return f"{self.public_url}/{self._key(key)}"
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": self._key(key)},
            ExpiresIn=int(expires or self.presign_seconds),
        )

    def delete(self, key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        return True

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except Exception:
            return False

    async def url_async(self, key: str, expires: Optional[int] = None) -> str:
        return await asyncio.to_thread(self.url, key, expires)


_STORAGE: dict = {}


def storage(driver: Optional[str] = None):
    """The configured storage (``STORAGE_DRIVER``), cached per driver."""
    name = (driver or str(ENV_CONFIG.get("STORAGE_DRIVER", "local") or "local")).lower()
    if name not in _STORAGE:
        if name == "s3":
            _STORAGE[name] = S3Storage()
        elif name == "local":
            _STORAGE[name] = LocalStorage()
        else:
            raise ValueError(f"Unknown STORAGE_DRIVER '{name}' (local or s3)")
    return _STORAGE[name]


def set_storage(instance: Any, driver: Optional[str] = None) -> None:
    """Replace the storage (tests, custom drivers)."""
    _STORAGE[(driver or instance.driver).lower()] = instance
