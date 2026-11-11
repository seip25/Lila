"""Lila static file serving with compression that never runs twice.

- ``LilaStaticFiles`` serves ``file.js.br`` / ``file.js.gz`` produced by
  ``lila optimize`` when the client accepts them, and otherwise compresses
  text assets (JS, CSS, SVG, JSON, HTML...) **once** and keeps the result in a
  small LRU keyed by path + mtime. Images and fonts are never compressed.
- ``bundled_js_response`` serves ``/js/lila-client.js`` and ``/js/ws.js`` from
  the installed package: minified with ``rjsmin`` when available and not in
  debug, compressed, cached, with ETag/304.

The global GZip middleware skips every static path, so a request costs a dict
lookup instead of a gzip pass in Python.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import threading
from collections import OrderedDict
from typing import Optional, Tuple

from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles

try:  # optional: pip install brotli
    import brotli  # type: ignore

    HAS_BROTLI = True
except Exception:  # pragma: no cover - optional dependency
    brotli = None
    HAS_BROTLI = False

COMPRESSIBLE_TYPES = (
    "text/",
    "application/javascript",
    "application/json",
    "application/xml",
    "image/svg+xml",
    "application/manifest+json",
    "application/wasm",
)
MAX_COMPRESS_BYTES = 2 * 1024 * 1024
_CACHE_MAX_ITEMS = 128
_CACHE_MAX_BYTES = 24 * 1024 * 1024

_cache: "OrderedDict[tuple, bytes]" = OrderedDict()
_cache_bytes = 0
_lock = threading.Lock()


def accepted_encoding(accept_encoding: str) -> Optional[str]:
    """Returns ``br``, ``gzip`` or ``None`` (q=0 values are ignored)."""
    accepted = set()
    for part in (accept_encoding or "").lower().split(","):
        token, _, params = part.strip().partition(";")
        q = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        if token and q > 0:
            accepted.add(token)
    if "br" in accepted and HAS_BROTLI:
        return "br"
    if "gzip" in accepted:
        return "gzip"
    return None


def precompressed_encoding(accept_encoding: str) -> list:
    """Encodings to try for files already compressed on disk (``.br`` files need
    no brotli module to be served, only to be created)."""
    lowered = {p.strip().split(";")[0] for p in (accept_encoding or "").lower().split(",")}
    return [enc for enc in ("br", "gzip") if enc in lowered]


def is_compressible(media_type: str) -> bool:
    media_type = (media_type or "").split(";")[0].strip().lower()
    return media_type.startswith(COMPRESSIBLE_TYPES)


def compress(data: bytes, encoding: str) -> bytes:
    if encoding == "br" and HAS_BROTLI:
        return brotli.compress(data, quality=5)
    return gzip.compress(data, compresslevel=6)


def cached_compress(key: tuple, loader, encoding: str) -> bytes:
    """Compresses once per (key, encoding) and keeps the bytes in a bounded LRU."""
    global _cache_bytes
    cache_key = key + (encoding,)
    with _lock:
        hit = _cache.get(cache_key)
        if hit is not None:
            _cache.move_to_end(cache_key)
            return hit
    body = compress(loader(), encoding)
    with _lock:
        _cache[cache_key] = body
        _cache_bytes += len(body)
        while _cache and (len(_cache) > _CACHE_MAX_ITEMS or _cache_bytes > _CACHE_MAX_BYTES):
            _, old = _cache.popitem(last=False)
            _cache_bytes -= len(old)
    return body


def clear_cache() -> None:
    global _cache_bytes
    with _lock:
        _cache.clear()
        _cache_bytes = 0


_ENCODING_SUFFIX = {"br": ".br", "gzip": ".gz"}


class LilaStaticFiles(StaticFiles):
    """StaticFiles with precompressed siblings and cached on-the-fly compression."""

    def file_response(self, full_path, stat_result, scope, status_code: int = 200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        if response.status_code != 200 or not isinstance(response, FileResponse):
            return response

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if "range" in headers:
            return response
        accept = headers.get("accept-encoding", "")
        media_type = response.media_type or ""
        path = str(full_path)

        # 1. Files compressed ahead of time by `lila optimize`.
        for encoding in precompressed_encoding(accept):
            sibling = path + _ENCODING_SUFFIX[encoding]
            try:
                sibling_stat = os.stat(sibling)
            except OSError:
                continue
            if sibling_stat.st_mtime < stat_result.st_mtime:
                continue  # stale: the original changed after `lila optimize`
            pre = FileResponse(sibling, stat_result=sibling_stat, media_type=media_type)
            pre.headers["content-encoding"] = encoding
            pre.headers["vary"] = "Accept-Encoding"
            pre.headers["etag"] = response.headers.get("etag", "") + f'-{encoding}'
            pre.headers["last-modified"] = response.headers.get("last-modified", "")
            return pre

        # 2. Text assets compressed once and cached in memory.
        encoding = accepted_encoding(accept)
        if not encoding or not is_compressible(media_type) or stat_result.st_size > MAX_COMPRESS_BYTES:
            return response
        if stat_result.st_size < 512:
            return response

        def _load() -> bytes:
            with open(path, "rb") as fh:
                return fh.read()

        body = cached_compress((path, stat_result.st_mtime_ns, stat_result.st_size), _load, encoding)
        out = Response(content=body, media_type=media_type, status_code=200)
        out.headers["content-encoding"] = encoding
        out.headers["vary"] = "Accept-Encoding"
        for name in ("etag", "last-modified"):
            if name in response.headers:
                out.headers[name] = response.headers[name] + (f"-{encoding}" if name == "etag" else "")
        return out


# ──────────────────────────────────────────────────────────────────────────────
# Bundled client scripts (lila-client.js, ws.js)
# ──────────────────────────────────────────────────────────────────────────────
_bundled: dict = {}


def _minify_js(source: str) -> str:
    try:
        import rjsmin  # type: ignore

        return rjsmin.jsmin(source)
    except Exception:
        return source


def _bundled_variant(path: str, minify: bool) -> Tuple[bytes, str, float]:
    stat = os.stat(path)
    key = (path, stat.st_mtime_ns, minify)
    cached = _bundled.get(key)
    if cached is None:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        if minify:
            text = _minify_js(text)
        body = text.encode("utf-8")
        etag = hashlib.blake2b(body, digest_size=10).hexdigest()
        cached = (body, etag, stat.st_mtime)
        for old in [k for k in _bundled if k[0] == path]:
            _bundled.pop(old, None)
        _bundled[key] = cached
    return cached


def bundled_js_response(request, path: str, debug: bool) -> Response:
    """Serves a packaged script: minified (prod), compressed, ETag/304."""
    if not os.path.isfile(path):
        return Response(status_code=404)
    body, etag, _ = _bundled_variant(path, minify=not debug)
    encoding = accepted_encoding(request.headers.get("accept-encoding", ""))
    tag = f'W/"{etag}{"-" + encoding if encoding else ""}"'
    cache_control = "no-cache" if debug else "public, max-age=3600"
    headers = {"etag": tag, "cache-control": cache_control, "vary": "Accept-Encoding"}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=headers)
    if encoding:
        body = cached_compress((path, etag), lambda: body, encoding)
        headers["content-encoding"] = encoding
    return Response(content=body, media_type="application/javascript", headers=headers)
