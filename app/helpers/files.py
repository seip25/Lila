from app.config import PATH_UPLOADS 
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.logger import Logger 
from pathlib import Path  
from typing import Union, List, Set 
from PIL import Image
from app.helpers.translate import translate_




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
    # English: Handles file upload with validations and translations
    # Español: Maneja la subida de archivos con validaciones y traducciones
    """
    try:
        # English: Validate HTTP method
        # Español: Validar método HTTP
        if request.method != "POST":
            return JSONResponse(
                {
                    "error": True,
                    "success": False,
                    "message": translate_("invalid_method", request),
                },
                status_code=405,
            )

        # English: Validate content type
        # Español: Validar tipo de contenido
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return JSONResponse(
                {
                    "error": True,
                    "success": False,
                    "message": translate_("invalid_content_type", request),
                },
                status_code=400,
            )

        # English: Create upload directory if it doesn't exist
        # Español: Crear directorio de uploads si no existe
        upload_path = Path(UPLOAD_DIR)
        if not upload_path.exists():
            upload_path.mkdir(parents=True, exist_ok=True)

        try:
            form = await request.form()
            file = form.get(name_file)

            # English: Check if file exists in form
            # Español: Verificar si el archivo existe en el formulario
            if not file:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": translate_("file_not_found", request),
                    },
                    status_code=400,
                )

            # English: Handle multiple files
            # Español: Manejar múltiples archivos
            if isinstance(file, list):
                files = []
                for f in file:
                    # English: Validate file extension
                    # Español: Validar extensión del archivo
                    extension = f.filename.split(".")[-1].lower()
                    if extension not in ALLOWED_EXTENSIONS:
                        return JSONResponse(
                            {
                                "error": True,
                                "success": False,
                                "message": translate_("invalid_extension", request),
                            },
                            status_code=400,
                        )

                    # English: Validate file size
                    # Español: Validar tamaño del archivo
                    if f.size > MAX_FILE_SIZE:
                        return JSONResponse(
                            {
                                "error": True,
                                "success": False,
                                "message": translate_("file_too_large", request),
                            },
                            status_code=400,
                        )

                    # English: Validate file is not empty
                    # Español: Validar que el archivo no esté vacío
                    content = await f.read()
                    if len(content) == 0:
                        return JSONResponse(
                            {
                                "error": True,
                                "success": False,
                                "message": translate_("empty_file", request),
                            },
                            status_code=400,
                        )

                    # English: Save file with safe filename
                    # Español: Guardar archivo con nombre seguro
                    safe_filename = "".join(
                        c for c in f.filename if c.isalnum() or c in (" ", ".", "_")
                    ).rstrip()
                    file_path = upload_path / safe_filename

                    with open(file_path, "wb") as fp:
                        fp.write(content)

                    optimized_path = optimize_image(file_path,extension)
                    files.append(optimized_path)

                return JSONResponse(
                    {
                        "files": files,
                        "success": True,
                        "message": translate_("upload_success", request),
                    },
                    status_code=200,
                )

            # English: Handle single file (same validations as above)
            # Español: Manejar archivo único (mismas validaciones que arriba)
            extension = file.filename.split(".")[-1].lower()
            if extension not in ALLOWED_EXTENSIONS:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": translate_("invalid_extension", request),
                    },
                    status_code=400,
                )

            if file.size > MAX_FILE_SIZE:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": translate_("file_too_large", request),
                    },
                    status_code=400,
                )

            content = await file.read()
            if len(content) == 0:
                return JSONResponse(
                    {
                        "error": True,
                        "success": False,
                        "message": translate_("empty_file", request),
                    },
                    status_code=400,
                )

            safe_filename = "".join(
                c for c in file.filename if c.isalnum() or c in (" ", ".", "_")
            ).rstrip()
            file_path = upload_path / safe_filename

            with open(file_path, "wb") as fp:
                fp.write(content)

            file_path = optimize_image(file_path,extension)

            return JSONResponse(
                {
                    "file": str(file_path),
                    "success": True,
                    "message": translate_("upload_success", request),
                },
                status_code=200,
            )

        except Exception as e:
            Logger.error(str(e))
            return JSONResponse(
                {
                    "error": True,
                    "success": False,
                    "message": translate_("server_error", request),
                },
                status_code=400,
            )

    except Exception as e:
        Logger.error(str(e))
        return JSONResponse(
            {
                "error": True,
                "success": False,
                "message": translate_("server_error", request),
            },
            status_code=500,
        )


def optimize_image(file_path: Path, extension: str, max_width=1920, quality=75) -> Path:
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


