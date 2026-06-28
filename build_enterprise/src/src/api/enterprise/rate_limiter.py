# enterprise/rate_limiter.py – Redis-based distributed rate limiting
import redis
import time
import hashlib
from typing import Optional, Tuple
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

class RedisRateLimiter:
    def __init__(self, redis_url: str = "redis://localhost:6379/0", default_limit: int = 1000, window_seconds: int = 3600):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
    
    def _get_key(self, identifier: str, endpoint: str) -> str:
        return f"rate_limit:{identifier}:{endpoint}"
    
    def check_rate_limit(self, identifier: str, endpoint: str, limit: Optional[int] = None) -> Tuple[bool, int]:
        key = self._get_key(identifier, endpoint)
        current_limit = limit if limit is not None else self.default_limit
        now = int(time.time())
        window_start = now - self.window_seconds
        
        # Use Redis sorted set for sliding window
        self.redis_client.zremrangebyscore(key, 0, window_start)
        current_count = self.redis_client.zcard(key)
        
        if current_count >= current_limit:
            return False, current_count
        
        # Add current request
        self.redis_client.zadd(key, {str(now): now})
        self.redis_client.expire(key, self.window_seconds + 60)
        return True, current_count + 1
    
    def get_remaining(self, identifier: str, endpoint: str, limit: Optional[int] = None) -> int:
        key = self._get_key(identifier, endpoint)
        current_limit = limit if limit is not None else self.default_limit
        now = int(time.time())
        window_start = now - self.window_seconds
        self.redis_client.zremrangebyscore(key, 0, window_start)
        current_count = self.redis_client.zcard(key)
        return max(0, current_limit - current_count)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limiter: RedisRateLimiter, api_key_header: str = "X-API-Key"):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.api_key_header = api_key_header
    
    async def dispatch(self, request: Request, call_next):
        # Extract identifier (API key or IP)
        api_key = request.headers.get(self.api_key_header)
        identifier = api_key if api_key else request.client.host
        
        # Skip rate limiting for internal health checks
        if request.url.path in ["/v1/health", "/metrics", "/ready", "/live"]:
            return await call_next(request)
        
        is_allowed, count = self.rate_limiter.check_rate_limit(identifier, request.url.path)
        if not is_allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(self.rate_limiter.get_remaining(identifier, request.url.path))
        return response
