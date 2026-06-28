# apiversioning/handlers/versioned_handlers.py – Version‑specific endpoint implementations
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import json

# Versioned routers
v1_router = APIRouter()
v2_router = APIRouter()
v3_router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    modules: Dict[str, bool] = {}
    tier: str = "free_pay_per_use"

@v1_router.post("/chat", tags=["v1"])
async def chat_v1(req: ChatRequest, request: Request):
    """Legacy v1 endpoint – simpler response format"""
    # Legacy compatibility layer
    result = {"answer": f"Legacy v1: {req.query}", "legacy": True}
    return result

@v1_router.get("/health", tags=["v1"])
async def health_v1():
    return {"status": "v1_legacy"}

@v2_router.post("/chat", tags=["v2"])
async def chat_v2(req: ChatRequest, request: Request):
    """Current v2 endpoint – full features"""
    # Call CrownStar core (would use core.answer)
    # For demo:
    result = {
        "answer": f"CrownStar v2: {req.query}",
        "conversation_id": "demo-123",
        "latency_ms": 150,
        "modules_active": [m for m,en in req.modules.items() if en]
    }
    return result

@v2_router.get("/health", tags=["v2"])
async def health_v2():
    return {"status": "v2_current", "version": "2"}

@v3_router.post("/chat", tags=["v3"])
async def chat_v3(req: ChatRequest, request: Request):
    """Beta v3 endpoint – enhanced response with streaming support (stub)"""
    result = {
        "answer": f"CrownStar v3 (beta): {req.query}",
        "conversation_id": "demo-456",
        "latency_ms": 120,
        "modules_active": [m for m,en in req.modules.items() if en],
        "streaming_supported": True
    }
    return result

@v3_router.get("/health", tags=["v3"])
async def health_v3():
    return {"status": "v3_beta", "version": "3"}

def include_versioned_routers(app, base_path: str = ""):
    """Mount versioned routers with their base paths"""
    app.include_router(v1_router, prefix="/v1", tags=["v1"])
    app.include_router(v2_router, prefix="/v2", tags=["v2"])
    app.include_router(v3_router, prefix="/v3", tags=["v3"])
