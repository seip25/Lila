"""Lila Framework v2.0.0 Asynchronous File Uploader.
Validates file size, extensions, sanitizes filenames safely,
and optionally optimizes images to WebP if Pillow is installed.
"""

import os
import re
import uuid
from pathlib import Path
from typing import Union, List, Set, Optional, Dict, Any
from starlette.datastructures import UploadFile

from lila.core.config import get_data_path
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
    "txt", "pdf", "png", "jpg", "jpeg", "webp","mp4","mov","webm","avi","mkv","mp3","wav","ogg","flv","wmv","gif", "svg", "csv", "xlsx", "xls", "zip", "doc", "docx"
}
DEFAULT_MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename removing directory traversal and unsafe characters."""
    clean = os.path.basename(filename)
    name, ext = os.path.splitext(clean)
    name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)
    unique_suffix = uuid.uuid4().hex[:8]
    ext = ext.lower().strip()
    return f"{name}_{unique_suffix}{ext}"


async def upload(
    request: Request,
    name_file: str = "file",
    upload_dir: Optional[str] = None,
    allowed_extensions: Optional[Set[str]] = None,
    max_file_size: Optional[int] = None,
    convert_to_webp: bool = False,
    webp_quality: int = 80,
) -> Union[JSONResponse, Dict[str, Any]]:
    """Handles async file upload with validations, safe naming and optional WebP optimization."""
    target_dir = upload_dir or os.path.join(get_data_path(), "uploads")
    allowed = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    max_size = max_file_size or DEFAULT_MAX_FILE_SIZE

    if request.method != "POST":
        return JSONResponse({"success": False, "message": "Method not allowed. Use POST."}, status_code=405)

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return JSONResponse({"success": False, "message": "Expected multipart/form-data content type."}, status_code=400)

    os.makedirs(target_dir, exist_ok=True)

    try:
        form = await request.form()
        uploaded_item = form.get(name_file)
        if not uploaded_item:
            return JSONResponse({"success": False, "message": f"No file provided with field name '{name_file}'."}, status_code=400)

        items: List[UploadFile] = uploaded_item if isinstance(uploaded_item, list) else [uploaded_item]
        saved_files = []

        for item in items:
            raw_filename = item.filename or "uploaded_file"
            ext = raw_filename.split(".")[-1].lower() if "." in raw_filename else ""

            if ext not in allowed:
                return JSONResponse({"success": False, "message": f"File extension '.{ext}' is not permitted."}, status_code=400)

            content = await item.read()
            size = len(content)

            if size == 0:
                return JSONResponse({"success": False, "message": "Uploaded file is empty."}, status_code=400)

            if size > max_size:
                return JSONResponse({"success": False, "message": f"File exceeds maximum allowed size ({max_size // (1024*1024)}MB)."}, status_code=400)

            safe_name = sanitize_filename(raw_filename)
            dest_path = os.path.join(target_dir, safe_name)

            # WebP optimization if requested and Pillow is available
            if convert_to_webp and ext in ("jpg", "jpeg", "png") and HAS_PIL:
                import io
                try:
                    img = Image.open(io.BytesIO(content))
                    webp_name = os.path.splitext(safe_name)[0] + ".webp"
                    webp_path = os.path.join(target_dir, webp_name)
                    img.save(webp_path, "WEBP", quality=webp_quality)
                    saved_files.append({
                        "original_name": raw_filename,
                        "saved_name": webp_name,
                        "path": webp_path,
                        "size": os.path.getsize(webp_path),
                        "url": f"/uploads/{webp_name}",
                    })
                    continue
                except Exception as img_err:
                    Logger.warning(f"WebP conversion failed: {img_err}")

            with open(dest_path, "wb") as f:
                f.write(content)

            saved_files.append({
                "original_name": raw_filename,
                "saved_name": safe_name,
                "path": dest_path,
                "size": size,
                "url": f"/uploads/{safe_name}",
            })

        if len(saved_files) == 1:
            return {"success": True, **saved_files[0]}
        return {"success": True, "files": saved_files}

    except Exception as e:
        Logger.error(f"File upload error: {e}", exception=e)
        return JSONResponse({"success": False, "message": f"Upload failed: {str(e)}"}, status_code=500)
