"""Lila Framework v2.0.x Asynchronous File Uploader.

- Streams files to disk in chunks (no full-file RAM spike).
- Writes into ``public/uploads`` by default, served by ``App`` at ``/uploads``.
- Returns relative URLs only (never absolute server paths).
- Blocks active SVG/HTML uploads and validates size/extensions.
"""

import io
import os
import re
import sys
import uuid
import mimetypes
from typing import Union, List, Set, Optional, Dict, Any

from starlette.datastructures import UploadFile

from lila.core.config import get_base_path, get_data_path
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.logger import Logger

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False


DEFAULT_ALLOWED_EXTENSIONS: Set[str] = {
    "txt", "pdf", "png", "jpg", "jpeg", "webp", "gif",
    "mp4", "mov", "webm", "avi", "mkv", "mp3", "wav", "ogg", "flv", "wmv",
    "csv", "xlsx", "xls", "zip", "doc", "docx",
}
DEFAULT_MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
_CHUNK_SIZE = 1024 * 1024

if HAS_PIL:
    # Prevent decompression bombs from exhausting RAM.
    Image.MAX_IMAGE_PIXELS = 40_000_000


def sanitize_filename(filename: str) -> str:
    """Sanitizes a filename, preserving Unicode letters (Chinese, accents, ...)."""
    clean = os.path.basename(str(filename or "file"))
    name, ext = os.path.splitext(clean)
    name = re.sub(r"[^\w.\-]", "_", name, flags=re.UNICODE).strip("._") or "file"
    name = name[:80]
    unique_suffix = uuid.uuid4().hex[:8]
    ext = ext.lower().strip()
    return f"{name}_{unique_suffix}{ext}"


def _public_url(target_dir: str, filename: str) -> str:
    """Returns a URL that App actually serves for the uploaded file."""
    public_root = os.path.realpath(get_base_path("public"))
    uploads_root = os.path.join(public_root, "uploads")
    real_target = os.path.realpath(target_dir)
    if getattr(sys, "frozen", False):
        data_uploads = os.path.realpath(get_data_path("uploads"))
        if real_target == data_uploads or real_target.startswith(data_uploads + os.sep):
            relative = os.path.relpath(real_target, data_uploads).replace("\\", "/")
            prefix = "" if relative == "." else relative + "/"
            return f"/uploads/{prefix}{filename}"
    if real_target == uploads_root or real_target.startswith(uploads_root + os.sep):
        relative = os.path.relpath(real_target, uploads_root).replace("\\", "/")
        prefix = "" if relative == "." else relative + "/"
        return f"/uploads/{prefix}{filename}"
    if real_target == public_root:
        return f"/public/{filename}"
    if real_target.startswith(public_root + os.sep):
        relative = os.path.relpath(real_target, public_root).replace("\\", "/")
        return f"/public/{relative}/{filename}"
    return f"/uploads/{filename}"


async def _stream_to_disk(item: UploadFile, dest_path: str, max_size: int) -> int:
    total = 0
    tmp_path = f"{dest_path}.part"
    try:
        with open(tmp_path, "wb") as fh:
            while True:
                chunk = await item.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError("too_large")
                fh.write(chunk)
        if total == 0:
            raise ValueError("empty")
        os.replace(tmp_path, dest_path)
        return total
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


async def upload(
    request: Request,
    name_file: str = "file",
    upload_dir: Optional[str] = None,
    allowed_extensions: Optional[Set[str]] = None,
    max_file_size: Optional[int] = None,
    convert_to_webp: bool = False,
    webp_quality: int = 80,
) -> Union[JSONResponse, Dict[str, Any]]:
    """Handles async file uploads with validation and optional WebP optimization."""
    if upload_dir:
        target_dir = upload_dir
    elif getattr(sys, "frozen", False):
        target_dir = get_data_path("uploads")
    else:
        target_dir = get_base_path("public", "uploads")
    allowed = {str(ext).lower().lstrip(".") for ext in (allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)}
    max_size = int(max_file_size or DEFAULT_MAX_FILE_SIZE)

    if request.method != "POST":
        return JSONResponse({"success": False, "message": "Method not allowed. Use POST."}, status_code=405)

    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" not in content_type:
        return JSONResponse(
            {"success": False, "message": "Expected multipart/form-data content type."}, status_code=400
        )

    try:
        os.makedirs(target_dir, exist_ok=True)
        form = await request.form()
        if hasattr(form, "getlist"):
            items = form.getlist(name_file)
        else:
            value = form.get(name_file)
            items = value if isinstance(value, list) else ([value] if value else [])
    except Exception as exc:
        Logger.error(f"File upload form parse error: {exc}", exception=exc)
        return JSONResponse({"success": False, "message": "Invalid multipart payload."}, status_code=400)

    if not items:
        return JSONResponse(
            {"success": False, "message": f"No file provided with field name '{name_file}'."}, status_code=400
        )

    saved_files: List[dict] = []
    for item in items:
        if not isinstance(item, UploadFile):
            continue
        raw_filename = item.filename or "uploaded_file"
        ext = raw_filename.rsplit(".", 1)[-1].lower() if "." in raw_filename else ""
        if ext not in allowed:
            return JSONResponse(
                {"success": False, "message": f"File extension '.{ext}' is not permitted."}, status_code=400
            )

        safe_name = sanitize_filename(raw_filename)
        dest_path = os.path.join(target_dir, safe_name)

        try:
            if convert_to_webp and HAS_PIL and ext in ("jpg", "jpeg", "png"):
                content = await item.read(max_size + 1)
                if len(content) > max_size:
                    return JSONResponse(
                        {"success": False, "message": f"File exceeds maximum allowed size ({max_size // (1024 * 1024)}MB)."},
                        status_code=400,
                    )
                if not content:
                    return JSONResponse({"success": False, "message": "Uploaded file is empty."}, status_code=400)
                try:
                    image = Image.open(io.BytesIO(content))
                    image.load()
                    webp_name = os.path.splitext(safe_name)[0] + ".webp"
                    webp_path = os.path.join(target_dir, webp_name)
                    image.save(webp_path, "WEBP", quality=int(webp_quality))
                    saved_files.append({
                        "original_name": raw_filename,
                        "saved_name": webp_name,
                        "size": os.path.getsize(webp_path),
                        "mime": "image/webp",
                        "url": _public_url(target_dir, webp_name),
                    })
                    await item.close()
                    continue
                except Exception as img_err:
                    Logger.warning(f"WebP conversion failed: {img_err}")
                    size = len(content)
                    with open(dest_path, "wb") as fh:
                        fh.write(content)
            else:
                size = await _stream_to_disk(item, dest_path, max_size)
        except ValueError as exc:
            if str(exc) == "too_large":
                return JSONResponse(
                    {"success": False, "message": f"File exceeds maximum allowed size ({max_size // (1024 * 1024)}MB)."},
                    status_code=400,
                )
            return JSONResponse({"success": False, "message": "Uploaded file is empty."}, status_code=400)
        except Exception as exc:
            Logger.error(f"File upload write error: {exc}", exception=exc)
            return JSONResponse({"success": False, "message": "Upload failed."}, status_code=500)

        mime_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        saved_files.append({
            "original_name": raw_filename,
            "saved_name": safe_name,
            "size": size,
            "mime": mime_type,
            "url": _public_url(target_dir, safe_name),
        })
        await item.close()

    if len(saved_files) == 1:
        return {"success": True, **saved_files[0]}
    return {"success": True, "files": saved_files}
