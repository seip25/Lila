from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.logger import Logger

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            Logger.error(f"Unhandled Error: {str(e)}")
            return JSONResponse({"error": "Internal Server Error", "detail": str(e)}, status_code=500)
