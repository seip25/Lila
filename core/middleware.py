from starlette.middleware.base import BaseHTTPMiddleware
from core.responses import JSONResponse
from core.logger import Logger



class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request, call_next):
        try:
            Logger.info(await Logger.request(request=request))
            response = await call_next(request)
            return response
        except Exception as e:
            Logger.error(f"Unhandled Error: {str(e)}")
            return JSONResponse({"error": "Internal Server Error","success":False}, status_code=500)
