"""v1-compatible manual request parser.

The recommended v2 path is ``@router.post(..., model=Model)`` or a Pydantic
annotation on the handler. ``RequestParser`` remains for projects migrating from
Lila 1.x.
"""

from typing import Any, Dict, Type

from pydantic import BaseModel, ValidationError

from lila.core.routing import Translate


class RequestParser:
    async def parse_body(self, request: Any, model: Type[BaseModel]) -> Dict[str, Any]:
        try:
            content_type = request.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                data = await request.json()
            elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
                data = dict(await request.form())
            else:
                data = await request.json()
            validated = model.model_validate(data)
            return {"success": True, "data": validated, "errors": []}
        except ValidationError as exc:
            translated = Translate.format_errors(exc, request=request)
            return {"success": False, "data": None, "errors": translated}
        except Exception as exc:
            return {"success": False, "data": None, "errors": [{"body": str(exc)}]}
