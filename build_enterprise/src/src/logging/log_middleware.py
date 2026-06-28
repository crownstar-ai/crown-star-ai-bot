# logging/log_middleware.py – Request logging middleware (JSON)
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from .structured_logger import get_logger, RequestContextFilter
import logging

logger = get_logger("crownstar.http")

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        trace_id = request.headers.get("X-Trace-ID", request_id)
        
        # Add context to logger
        ctx_filter = RequestContextFilter()
        
        start_time = time.perf_counter()
        
        # Log request
        logger.info("Request started", extra={
            "request_id": request_id,
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client_ip": request.client.host if request.client else "unknown"
        })
        
        # Add trace ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log response
        logger.info("Request completed", extra={
            "request_id": request_id,
            "trace_id": trace_id,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2)
        })
        
        return response
