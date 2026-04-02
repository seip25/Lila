import orjson
from starlette.responses import (
    Response,
    HTMLResponse as StarletteHTMLResponse,
    RedirectResponse as StarletteRedirectResponse,
    PlainTextResponse as StarlettePlainTextResponse,
    StreamingResponse as StarletteStreamingResponse,
)
from decimal import Decimal
from pydantic import BaseModel
from typing import Any, Union

HTMLResponse = StarletteHTMLResponse
RedirectResponse = StarletteRedirectResponse
PlainTextResponse = StarlettePlainTextResponse
StreamingResponse = StarletteStreamingResponse


def _default_encoder(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, (set, tuple)):
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
        super().__init__(content, status_code, headers, media_type)

    def render(self, content: Any) -> bytes:
        return orjson_dumps(content)
