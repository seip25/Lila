import orjson
from starlette.responses import (
    Response,
    HTMLResponse as StarletteHTMLResponse,
    RedirectResponse as StarletteRedirectResponse,
    PlainTextResponse as StarlettePlainTextResponse,
    StreamingResponse as StarletteStreamingResponse,
    FileResponse as StarletteFileResponse,
)
from decimal import Decimal
from pydantic import BaseModel
from typing import Any, Union

class LilaResponseMixin:
    def __init__(self, *args, **kwargs):
        headers = kwargs.get("headers")
        if not headers:
            kwargs["headers"] = {"Powered-By": "Lila Framework"}
        elif "Powered-By" not in headers:
            headers["Powered-By"] = "Lila Framework"
        super().__init__(*args, **kwargs)

class HTMLResponse(LilaResponseMixin, StarletteHTMLResponse):
    pass

class RedirectResponse(LilaResponseMixin, StarletteRedirectResponse):
    pass

class PlainTextResponse(LilaResponseMixin, StarlettePlainTextResponse):
    pass

class StreamingResponse(LilaResponseMixin, StarletteStreamingResponse):
    pass

class FileResponse(LilaResponseMixin, StarletteFileResponse):
    pass


def _default_encoder(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    try:
        if hasattr(obj, "__dict__"):
            return vars(obj)
    except Exception:
        pass
    return str(obj)


def orjson_dumps(content: Any) -> bytes:
    return orjson.dumps(
        content,
        default=_default_encoder,
        option=orjson.OPT_NON_STR_KEYS, 
    )

def orjson_loads(content: Union[str, bytes]) -> Any:
    return orjson.loads(content)


class JSONResponse(Response):
    media_type = "application/json"

    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict = None,
        media_type: str = None,
    ) -> None:
        if not headers:
            headers = {"Powered-By": "Lila Framework"}
        elif "Powered-By" not in headers:
            headers["Powered-By"] = "Lila Framework"
        super().__init__(content, status_code, headers, media_type)

    def render(self, content: Any) -> bytes:
        return orjson_dumps(content)

    @staticmethod
    def validation_error(e):
        """Standardized response for Pydantic validation errors."""
        errors = []
        msg_errors = ""
        try:
            for err in e.errors():
                field = err["loc"][-1] if err["loc"] else "unknown"
                msg = err["msg"]
                errors.append({str(field): msg})
                msg_errors += f"{field} : {msg} . "
        except Exception:
            msg_errors = str(e)

        return JSONResponse(
            {"success": False, "errors": errors, "msg": msg_errors},
            status_code=400,
        )
