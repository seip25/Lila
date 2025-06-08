from core.request import Request
from core.responses import JSONResponse
from pydantic import BaseModel, ValidationError


class Controller:
    async def parse_request(
        self, request: Request, schema: BaseModel, response: JSONResponse = None
    ):
        try:
            body = await request.json()
            return schema(**body)
        except ValidationError as e:
            if response:
                return response(
                    status_code=400,
                    content={"error": True, "details": e.errors()},
                )
            return False
        except Exception as e:
            if response:
                return response(
                    status_code=400,
                    content={"error": True, "details": e.errors()},
                )
            return False
