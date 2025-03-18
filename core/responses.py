from starlette.responses import  JSONResponse as StarletteJSONResponse,HTMLResponse,RedirectResponse,PlainTextResponse,RedirectResponse,StreamingResponse
from decimal import Decimal
from datetime import date, datetime

 
HTMLResponse = HTMLResponse
RedirectResponse = RedirectResponse
PlainTextResponse = PlainTextResponse
RedirectResponse=RedirectResponse
StreamingResponse=StreamingResponse

def convert_to_serializable(obj):
    if isinstance(obj, (Decimal)):
        return float(obj) 
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()  
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif hasattr(obj, "__dict__"):  
        return convert_to_serializable(obj.__dict__)
    else:
        return obj 

class JSONResponse(StarletteJSONResponse):
    def __init__(self, data, status_code=200,serialize=True):
        serialized_data = convert_to_serializable(data) if serialize else data
        super().__init__(serialized_data, status_code=status_code)
