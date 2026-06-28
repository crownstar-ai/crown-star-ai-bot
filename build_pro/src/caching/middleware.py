# caching/middleware.py – FastAPI middleware for automatic response caching
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .cache_service import get_cache
from .cdn import get_cdn
import time
import json

class CacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache_ttl: int = 300, exempt_paths: list = None):
        super().__init__(app)
        self.cache = get_cache()
        self.cdn = get_cdn()
        self.cache_ttl = cache_ttl
        self.exempt_paths = exempt_paths or ["/v1/chat", "/metrics", "/health"]
    
    async def dispatch(self, request: Request, call_next):
        # Skip caching for exempt paths or non‑GET methods
        if request.method != "GET" or any(request.url.path.startswith(p) for p in self.exempt_paths):
            return await call_next(request)
        
        # Try cache
        cache_key = f"http:{request.method}:{request.url.path}"
        if request.query_params:
            cache_key += f":{sorted(request.query_params.items())}"
        cached = self.cache.get("http", cache_key)
        if cached:
            return Response(content=cached, media_type="application/json", headers={
                "X-Cache": "HIT",
                "X-Cache-Source": "Redis/L1"
            })
        
        # Miss – generate response
        response = await call_next(request)
        
        # Only cache successful responses
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            self.cache.set("http", body.decode('utf-8'), cache_key, ttl=self.cache_ttl)
            # Reconstruct response
            new_response = Response(content=body, status_code=response.status_code, headers=dict(response.headers))
            new_response.headers["X-Cache"] = "MISS"
            # Add CDN headers
            cdn_headers = self.cdn.get_cache_headers(max_age=self.cache_ttl)
            for k, v in cdn_headers.items():
                new_response.headers[k] = v
            return new_response
        return response
