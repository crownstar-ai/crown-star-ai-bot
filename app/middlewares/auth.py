from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.security import decode_token

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Public paths
        if request.url.path in ["/", "/health", "/api/docs", "/api/redoc", "/api/openapi.json"]:
            return await call_next(request)
        if request.url.path.startswith("/api/v1/auth"):
            return await call_next(request)
        
        response = await call_next(request)
        return response
