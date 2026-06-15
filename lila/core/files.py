from app.config import PATH_UPLOADS 
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.logger import Logger 
from lila.core.translate import Translate
from pathlib import Path  
from typing import Union, List, Set 
from PIL import Image

ALLOWED_EXTENSIONS_ = {"txt", "pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE_ = 10 * 1024 * 1024  # 10MB


async def upload(
    request: Request,
    name_file: Union[str, List[str]] = "file",
    UPLOAD_DIR: str = PATH_UPLOADS,
    ALLOWED_EXTENSIONS: Set[str] = ALLOWED_EXTENSIONS_,
    MAX_FILE_SIZE: int = MAX_FILE_SIZE_,
):
    """
    Handles file upload with validations and translations.
    Maneja la subida de archivos con validaciones y traducciones.
    """
    try:
        if request.method != "POST":
            return JSONResponse(
                {
                    "error": True,
                    "success": False,
                    "message": Translate.t("invalid_method", request),
                },
                status_code=405,
            )

        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return JSONResponse(
                {
                    "error": True,
                    "success": False,
                    "message": Translate.t("invalid_content_type", request),
                },
                status_code=400,
            )

        upload_path = Path(UPLOAD_DIR)
        if not upload_path.exists():
            upload_path.mkdir(parents=True, exist_ok=True)

        try:
            form = await request.form()
            file = form.get(name_file)

            if not file:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": Translate.t("file_not_found", request),
                    },
                    status_code=400,
                )

            if isinstance(file, list):
                files = []
                for f in file:
                    extension = f.filename.split(".")[-1].lower()
                    if extension not in ALLOWED_EXTENSIONS:
                        return JSONResponse(
                            {
                                "error": True,
                                "success": False,
                                "message": Translate.t("invalid_extension", request),
                            },
                            status_code=400,
                        )

                    if f.size > MAX_FILE_SIZE:
                        return JSONResponse(
                            {
                                "error": True,
                                "success": False,
                                "message": Translate.t("file_too_large", request),
                            },
                            status_code=400,
                        )

                    content = await f.read()
                    if len(content) == 0:
                        return JSONResponse(
                            {
                                "error": True,
                                "success": False,
                                "message": Translate.t("empty_file", request),
                            },
                            status_code=400,
                        )

                    safe_filename = "".join(
                        c for c in f.filename if c.isalnum() or c in (" ", ".", "_")
                    ).rstrip()
                    file_path = upload_path / safe_filename

                    with open(file_path, "wb") as fp:
                        fp.write(content)

                    optimized_path = optimize_image(file_path, extension)
                    files.append(str(optimized_path))

                return JSONResponse(
                    {
                        "files": files,
                        "success": True,
                        "message": Translate.t("upload_success", request),
                    },
                    status_code=200,
                )

            extension = file.filename.split(".")[-1].lower()
            if extension not in ALLOWED_EXTENSIONS:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": Translate.t("invalid_extension", request),
                    },
                    status_code=400,
                )

            if file.size > MAX_FILE_SIZE:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": Translate.t("file_too_large", request),
                    },
                    status_code=400,
                )

            content = await file.read()
            if len(content) == 0:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": Translate.t("empty_file", request),
                    },
                    status_code=400,
                )

            safe_filename = "".join(
                c for c in file.filename if c.isalnum() or c in (" ", ".", "_")
            ).rstrip()
            file_path = upload_path / safe_filename

            with open(file_path, "wb") as fp:
                fp.write(content)

            file_path = optimize_image(file_path, extension)

            return JSONResponse(
                {
                    "file": str(file_path),
                    "success": True,
                    "message": Translate.t("upload_success", request),
                },
                status_code=200,
            )

        except Exception as e:
            Logger.error(str(e))
            return JSONResponse(
                {
                    "error": True,
                    "success": False,
                    "message": Translate.t("server_error", request),
                },
                status_code=400,
            )

    except Exception as e:
        Logger.error(str(e))
        return JSONResponse(
            {
                "error": True,
                "success": False,
                "message": Translate.t("server_error", request),
            },
            status_code=500,
        )


def optimize_image(file_path: Path, extension: str, max_width=1920, quality=75) -> Path:
    """Optimizes an image and saves it as WebP if possible."""
    try:
        img = Image.open(file_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        optimized_filename = f"{file_path.stem}.webp"
        optimized_path = file_path.parent / optimized_filename

        if extension.lower() in ["jpg", "jpeg", "png"]:
            img.save(optimized_path, format="WEBP", optimize=True, quality=quality)
        else:
            img.save(optimized_path, format=img.format, optimize=True, quality=quality)

        return optimized_path
    except Exception as e:
        Logger.error(f"Error optimizing image: {str(e)}")
        return file_path
