from typing import Union
from pydantic import BaseModel, ValidationError
from core.request import Request

class RequestParser:
    async def parse_body(self, request: Request, schema: BaseModel) -> dict:
        try:
            body = await request.json()
            model = schema(**body)
            return {"success": True, "data": model}
        except ValidationError as e:
            return {"success": False, "errors": e.errors()}
        except Exception as e:
            return {"success": False, "errors": [{"msg": str(e)}]}

    async def parse_query(self, request: Request, schema: BaseModel) -> dict:
        try:
            query_dict = dict(request.query_params)
            model = schema(**query_dict)
            return {"success": True, "data": model}
        except ValidationError as e:
            return {"success": False, "errors": e.errors()}
        except Exception as e:
            return {"success": False, "errors": [{"msg": str(e)}]}
