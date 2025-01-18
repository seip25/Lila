from core.request import Request
from core.responses import JSONResponse
from pydantic import BaseModel, ValidationError

class Controller:
    async def parse_request(self, request: Request, schema: BaseModel):
        try:
            body = await request.json()
            return schema(**body)
        except ValidationError as e:
            return False
        except Exception as e:
            print(e)
            return False
