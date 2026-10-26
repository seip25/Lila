"""Lila Response Classes.
Ultra-fast responses powered by orjson with Pydantic v2 support.
"""

from typing import Any, Union, Optional
from decimal import Decimal
import datetime
import uuid

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    orjson = None
    HAS_ORJSON = False

from starlette.responses import (
    Response,
    HTMLResponse as StarletteHTMLResponse,
    RedirectResponse as StarletteRedirectResponse,
    PlainTextResponse as StarlettePlainTextResponse,
    StreamingResponse as StarletteStreamingResponse,
    FileResponse as StarletteFileResponse,
)


class LilaResponseMixin:
    def __init__(self, *args, **kwargs):
        headers = kwargs.get("headers")
        if not headers:
            kwargs["headers"] = {"X-Powered-By": "Lila Framework 2.0"}
        elif "X-Powered-By" not in headers:
            kwargs["headers"] = dict(headers)
            kwargs["headers"]["X-Powered-By"] = "Lila Framework 2.0"
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
    # Pydantic v2 support
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, "__dict__"):
        return vars(obj)
    return str(obj)


def orjson_dumps(content: Any) -> bytes:
    if HAS_ORJSON:
        return orjson.dumps(
            content,
            default=_default_encoder,
            option=orjson.OPT_NON_STR_KEYS,
        )
    import json
    return json.dumps(content, default=_default_encoder).encode("utf-8")


def orjson_loads(content: Union[str, bytes]) -> Any:
    if HAS_ORJSON:
        return orjson.loads(content)
    import json
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    return json.loads(content)


class JSONResponse(Response):
    media_type = "application/json"

    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: Optional[dict] = None,
        media_type: Optional[str] = None,
    ) -> None:
        if not headers:
            headers = {"X-Powered-By": "Lila Framework 2.0"}
        elif "X-Powered-By" not in headers:
            headers = dict(headers)
            headers["X-Powered-By"] = "Lila Framework 2.0"
        super().__init__(content, status_code, headers, media_type)

    def render(self, content: Any) -> bytes:
        return orjson_dumps(content)

    @staticmethod
    def validation_error(e: Any, translated_errors: Optional[list] = None) -> "JSONResponse":
        """Standardized response for Pydantic validation errors."""
        errors = []
        msg_errors = ""
        if translated_errors:
            errors = translated_errors
            msg_errors = " | ".join(
                [f"{list(item.keys())[0]}: {list(item.values())[0]}" for item in errors]
            )
        else:
            try:
                for err in e.errors():
                    field = err["loc"][-1] if err["loc"] else "unknown"
                    msg = err.get("msg", "Invalid value")
                    errors.append({str(field): msg})
                    msg_errors += f"{field}: {msg}. "
            except Exception:
                msg_errors = str(e)

        return JSONResponse(
            {"success": False, "errors": errors, "msg": msg_errors.strip()},
            status_code=422,
        )
