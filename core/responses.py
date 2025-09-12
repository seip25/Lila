from starlette.responses import  JSONResponse as StarletteJSONResponse,HTMLResponse,RedirectResponse,PlainTextResponse,RedirectResponse,StreamingResponse
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel
 
HTMLResponse = HTMLResponse
RedirectResponse = RedirectResponse
PlainTextResponse = PlainTextResponse
RedirectResponse=RedirectResponse
StreamingResponse=StreamingResponse

def convert_to_serializable(obj):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return convert_to_serializable(obj.dict())
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [convert_to_serializable(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return convert_to_serializable(vars(obj))
    return str(obj)
 

class JSONResponse(StarletteJSONResponse):
    def __init__(self, data, status_code=200, serialize=True, headers=None):
        if serialize:
            data = convert_to_serializable(data)
        super().__init__(data, status_code=status_code, headers=headers)
