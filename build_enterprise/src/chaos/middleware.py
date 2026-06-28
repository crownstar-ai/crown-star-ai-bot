# chaos/middleware.py – FastAPI middleware for injecting faults
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import os
import random
import time

class ChaosMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check for latency injection
        latency_ms = os.environ.get("CHAOS_LATENCY_MS")
        if latency_ms:
            await asyncio.sleep(float(latency_ms) / 1000.0)
        
        # Check for error injection
        error_rate = os.environ.get("CHAOS_ERROR_RATE")
        if error_rate and random.random() < float(error_rate):
            return Response(
                content='{"error": "Chaos injection: simulated error"}',
                status_code=500,
                media_type="application/json"
            )
        
        response = await call_next(request)
        return response

# Import asyncio for sleep
import asyncio
