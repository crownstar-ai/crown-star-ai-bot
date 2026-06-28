# ====================================================================================================
# routes.py – CrownStar‑Absolute API Routes (FastAPI)
# Contains all endpoint definitions: /chat, /health, /metrics, /conversations, /export, /admin
# Designed to be mounted in app.py or used standalone.
# ====================================================================================================

import asyncio
import json
import time
import uuid
import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, status
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Pydantic models for request/response validation
# --------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    tier: str = "enterprise"
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    min_length: Optional[int] = Field(None, ge=1, le=2048)
    max_length: Optional[int] = Field(None, ge=10, le=8192)
    mode: str = Field("regal_futurism", pattern="^(regal_futurism|technical|minimal|custom)$")
    stream: bool = False
    conversation_id: Optional[str] = None
    
    @validator('max_length')
    def max_length_gt_min(cls, v, values):
        if v is not None and values.get('min_length') is not None and v <= values['min_length']:
            raise ValueError('max_length must be greater than min_length')
        return v

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    tokens_used: int
    tier: str
    latency_ms: float
    model_version: str = "1.0.0"

class ConversationMetadata(BaseModel):
    id: str
    title: str
    created: float
    updated: float
    message_count: int
    preview: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    code: str
    details: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)

class HealthResponse(BaseModel):
    status: str
    version: str
    tier: str
    uptime_seconds: float
    gpu_available: bool
    model_loaded: bool
    index_size: int
    memory_entries: int

# --------------------------------------------------------------------
# Authentication dependency placeholders (actual integration with security module)
# --------------------------------------------------------------------
async def get_current_user(api_key: Optional[str] = None, bearer: Optional[str] = None):
    """Placeholder – actual implementation uses src.security.api_auth."""
    # In production, this would validate JWT or API key
    return {"user_id": "default", "scopes": ["api:all"], "tier": "enterprise"}

async def get_optional_user(api_key: Optional[str] = None):
    return None

# --------------------------------------------------------------------
# Create router
# --------------------------------------------------------------------
router = APIRouter(prefix="/v1", tags=["CrownStar API"])

# --------------------------------------------------------------------
# Core endpoint: /chat (non-streaming)
# --------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse, summary="Send a message to CrownStar")
@router.post("/chat/completions", response_model=ChatResponse, include_in_schema=False)
async def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    user: Dict = Depends(get_current_user)
):
    """
    Send a message to CrownStar‑Absolute and receive a response.
    Supports tier selection, temperature, length limits, and expression modes.
    """
    start_time = time.perf_counter()
    
    # Get core instance from app state (injected by app.py)
    from fastapi import FastAPI
    from starlette.requests import Request as StarletteRequest
    # This will be provided by the parent app; for now use a placeholder
    # In actual implementation, core is accessed via request.app.state.core
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        # Fallback – should not happen in production
        from src.core.crownstar_core import CrownStarCore
        core_instance = CrownStarCore(lazy_load=False)
    
    # Apply overrides
    original_tier = core_instance.shell.state.tier
    original_temp = core_instance.shell.state.temperature
    original_min = core_instance.shell.state.min_length
    original_max = core_instance.shell.state.max_length
    original_mode = core_instance.shell.state.mode
    
    try:
        if request.tier:
            core_instance.shell.state.tier = request.tier
        if request.temperature:
            core_instance.shell.state.temperature = request.temperature
        if request.min_length:
            core_instance.shell.state.min_length = request.min_length
        if request.max_length:
            core_instance.shell.state.max_length = request.max_length
        if request.mode:
            core_instance.shell.set_mode(request.mode)
        
        # Use conversation ID if provided
        conv_id = request.conversation_id
        if conv_id:
            # Load conversation into shell (if method exists)
            if hasattr(core_instance.shell, 'load_conversation'):
                await core_instance.shell.load_conversation(conv_id)
        
        # Generate response
        response_text = await core_instance.answer(request.query, tier=request.tier)
        
        # Get conversation ID (new or existing)
        if hasattr(core_instance.shell, 'get_conversation_id'):
            conv_id = core_instance.shell.get_conversation_id()
        elif not conv_id:
            conv_id = str(uuid.uuid4())
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        tokens_used = len(response_text) // 4  # Approximate
        
        # Record telemetry in background
        background_tasks.add_task(
            record_telemetry,
            query=request.query,
            response=response_text,
            tier=request.tier,
            latency_ms=latency_ms,
            tokens=tokens_used
        )
        
        return ChatResponse(
            response=response_text,
            conversation_id=conv_id,
            tokens_used=tokens_used,
            tier=request.tier,
            latency_ms=latency_ms
        )
    finally:
        # Restore original settings
        core_instance.shell.state.tier = original_tier
        core_instance.shell.state.temperature = original_temp
        core_instance.shell.state.min_length = original_min
        core_instance.shell.state.max_length = original_max
        if original_mode:
            core_instance.shell.set_mode(original_mode)

# --------------------------------------------------------------------
# Streaming chat endpoint (Server‑Sent Events)
# --------------------------------------------------------------------
@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Stream the response token by token using Server‑Sent Events.
    """
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        from src.core.crownstar_core import CrownStarCore
        core_instance = CrownStarCore(lazy_load=False)
    
    async def event_generator():
        # Apply overrides (similar to non‑streaming)
        original_tier = core_instance.shell.state.tier
        original_temp = core_instance.shell.state.temperature
        original_min = core_instance.shell.state.min_length
        original_max = core_instance.shell.state.max_length
        original_mode = core_instance.shell.state.mode
        
        try:
            if request.tier:
                core_instance.shell.state.tier = request.tier
            if request.temperature:
                core_instance.shell.state.temperature = request.temperature
            if request.min_length:
                core_instance.shell.state.min_length = request.min_length
            if request.max_length:
                core_instance.shell.state.max_length = request.max_length
            if request.mode:
                core_instance.shell.set_mode(request.mode)
            
            # For streaming, we need to simulate tokens. In a real implementation,
            # we would hook into the model's generation to yield each token.
            # Here we simulate by splitting the final response.
            full_response = await core_instance.answer(request.query, tier=request.tier)
            # Simulate token streaming (split by words)
            words = full_response.split()
            for i, word in enumerate(words):
                # Add space after word except last
                token = word + (" " if i < len(words)-1 else "")
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                await asyncio.sleep(0.03)  # Simulate generation delay
            yield f"data: {json.dumps({'done': True, 'full_response': full_response})}\n\n"
        finally:
            core_instance.shell.state.tier = original_tier
            core_instance.shell.state.temperature = original_temp
            core_instance.shell.state.min_length = original_min
            core_instance.shell.state.max_length = original_max
            if original_mode:
                core_instance.shell.set_mode(original_mode)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --------------------------------------------------------------------
# Health endpoint
# --------------------------------------------------------------------
@router.get("/health", response_model=HealthResponse, tags=["System"])
@router.get("/healthz", include_in_schema=False)
async def health_endpoint(request: Request):
    """
    Returns the health status of the server and core components.
    Used by load balancers and monitoring systems.
    """
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        core_instance = None
    
    uptime = time.time() - getattr(request.app.state, 'start_time', time.time())
    
    if core_instance:
        stats = core_instance.get_stats() if hasattr(core_instance, 'get_stats') else {}
        model_loaded = core_instance.model is not None
        gpu_available = hasattr(torch, 'cuda') and torch.cuda.is_available()
        index_size = stats.get('index_size', 0)
        memory_entries = stats.get('memory_size', 0)
        tier = core_instance.shell.state.tier if core_instance.shell else "unknown"
    else:
        model_loaded = False
        gpu_available = False
        index_size = 0
        memory_entries = 0
        tier = "unknown"
    
    return HealthResponse(
        status="ok" if model_loaded else "degraded",
        version="1.0.0",
        tier=tier,
        uptime_seconds=uptime,
        gpu_available=gpu_available,
        model_loaded=model_loaded,
        index_size=index_size,
        memory_entries=memory_entries
    )

# --------------------------------------------------------------------
# Metrics endpoint (Prometheus format)
# --------------------------------------------------------------------
@router.get("/metrics", tags=["System"])
async def metrics_endpoint(request: Request):
    """
    Prometheus‑compatible metrics endpoint.
    Exposes key performance indicators: request count, latency, memory usage, etc.
    """
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        core_instance = None
    
    metrics_lines = []
    
    # Basic info
    metrics_lines.append("# HELP crownstar_build_info Build information")
    metrics_lines.append("# TYPE crownstar_build_info gauge")
    metrics_lines.append('crownstar_build_info{version="1.0.0",tier="enterprise"} 1')
    
    if core_instance:
        # Model parameters
        if core_instance.model:
            params = sum(p.numel() for p in core_instance.model.parameters())
            metrics_lines.append("# HELP crownstar_model_parameters Number of model parameters")
            metrics_lines.append("# TYPE crownstar_model_parameters gauge")
            metrics_lines.append(f"crownstar_model_parameters {params}")
        
        # Index size
        if core_instance.index:
            idx_size = core_instance.index.index.ntotal if hasattr(core_instance.index, 'index') else 0
            metrics_lines.append("# HELP crownstar_index_size Number of vectors in FAISS index")
            metrics_lines.append("# TYPE crownstar_index_size gauge")
            metrics_lines.append(f"crownstar_index_size {idx_size}")
        
        # Memory entries
        if core_instance.memory:
            mem_count = len(core_instance.memory.memories) if hasattr(core_instance.memory, 'memories') else 0
            metrics_lines.append("# HELP crownstar_memory_entries Number of stored memory entries")
            metrics_lines.append("# TYPE crownstar_memory_entries gauge")
            metrics_lines.append(f"crownstar_memory_entries {mem_count}")
        
        # GPU memory (if available)
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                mem_alloc = torch.cuda.memory_allocated(i) / 1024**2
                mem_res = torch.cuda.memory_reserved(i) / 1024**2
                metrics_lines.append(f"# HELP crownstar_gpu_memory_allocated_mb GPU memory allocated (MiB)")
                metrics_lines.append(f"# TYPE crownstar_gpu_memory_allocated_mb gauge")
                metrics_lines.append(f'crownstar_gpu_memory_allocated_mb{{device="{i}"}} {mem_alloc:.2f}')
                metrics_lines.append(f'crownstar_gpu_memory_reserved_mb{{device="{i}"}} {mem_res:.2f}')
    
    # System metrics
    import psutil
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    metrics_lines.append("# HELP crownstar_cpu_usage_percent CPU usage percentage")
    metrics_lines.append("# TYPE crownstar_cpu_usage_percent gauge")
    metrics_lines.append(f"crownstar_cpu_usage_percent {cpu_percent}")
    metrics_lines.append("# HELP crownstar_memory_usage_bytes System memory usage (bytes)")
    metrics_lines.append("# TYPE crownstar_memory_usage_bytes gauge")
    metrics_lines.append(f"crownstar_memory_usage_bytes {mem.used}")
    metrics_lines.append("# HELP crownstar_memory_available_bytes Available memory (bytes)")
    metrics_lines.append("# TYPE crownstar_memory_available_bytes gauge")
    metrics_lines.append(f"crownstar_memory_available_bytes {mem.available}")
    
    return Response(content="\n".join(metrics_lines), media_type="text/plain")

# --------------------------------------------------------------------
# Conversation management endpoints
# --------------------------------------------------------------------
@router.get("/conversations", response_model=List[ConversationMetadata], tags=["Conversations"])
async def list_conversations(request: Request, user: Dict = Depends(get_current_user)):
    """List all conversations for the authenticated user."""
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        return []
    
    if hasattr(core_instance.shell, 'list_conversations'):
        convs = core_instance.shell.list_conversations()
        return [ConversationMetadata(**c) for c in convs]
    return []

@router.get("/conversations/{conv_id}", tags=["Conversations"])
async def get_conversation(conv_id: str, request: Request, user: Dict = Depends(get_current_user)):
    """Retrieve full conversation history by ID."""
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        raise HTTPException(status_code=503, detail="Core not available")
    
    if hasattr(core_instance.shell, 'get_conversation'):
        messages = core_instance.shell.get_conversation(conv_id)
        if messages is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"conversation_id": conv_id, "messages": messages}
    raise HTTPException(status_code=501, detail="Conversation management not implemented")

@router.delete("/conversations/{conv_id}", tags=["Conversations"])
async def delete_conversation(conv_id: str, request: Request, user: Dict = Depends(get_current_user)):
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        raise HTTPException(status_code=503)
    
    if hasattr(core_instance.shell, 'delete_conversation'):
        success = core_instance.shell.delete_conversation(conv_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"success": True}
    raise HTTPException(status_code=501)

@router.post("/conversations/{conv_id}/rename", tags=["Conversations"])
async def rename_conversation(conv_id: str, title: str, request: Request, user: Dict = Depends(get_current_user)):
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        raise HTTPException(status_code=503)
    
    if hasattr(core_instance.shell, 'rename_conversation'):
        success = core_instance.shell.rename_conversation(conv_id, title)
        if not success:
            raise HTTPException(status_code=404)
        return {"success": True}
    raise HTTPException(status_code=501)

@router.post("/conversations/{conv_id}/export", tags=["Conversations"])
async def export_conversation(conv_id: str, format: str = "json", request: Request = None, user: Dict = Depends(get_current_user)):
    """
    Export a conversation in JSON, Markdown, or plain text format.
    """
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        raise HTTPException(status_code=503)
    
    if hasattr(core_instance.shell, 'export_conversation'):
        exported = core_instance.shell.export_conversation(conv_id, format)
        if exported is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        media_type = "application/json" if format == "json" else "text/markdown" if format == "markdown" else "text/plain"
        filename = f"conversation_{conv_id}.{ 'json' if format=='json' else 'md' if format=='markdown' else 'txt'}"
        return Response(content=exported, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    raise HTTPException(status_code=501)

# --------------------------------------------------------------------
# Admin endpoints (require elevated scope)
# --------------------------------------------------------------------
@router.post("/admin/clear_cache", tags=["Admin"])
async def admin_clear_cache(request: Request, user: Dict = Depends(get_current_user)):
    """Clear all caches (cortex, index memory). Requires admin scope."""
    if "admin" not in user.get("scopes", []):
        raise HTTPException(status_code=403, detail="Admin scope required")
    
    core = getattr(request, 'app', None)
    if core and hasattr(core, 'state') and hasattr(core.state, 'core'):
        core_instance = core.state.core
    else:
        raise HTTPException(status_code=503)
    
    if core_instance.cortex and hasattr(core_instance.cortex, '_harvest_cache'):
        core_instance.cortex._harvest_cache.clear()
    if core_instance.index and hasattr(core_instance.index, 'clear'):
        core_instance.index.clear()
    return {"success": True, "message": "Caches cleared"}

@router.post("/admin/gc", tags=["Admin"])
async def admin_garbage_collection(request: Request, user: Dict = Depends(get_current_user)):
    """Trigger garbage collection and CUDA cache clearing. Admin only."""
    if "admin" not in user.get("scopes", []):
        raise HTTPException(status_code=403)
    
    import gc
    gc.collect()
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {"success": True, "message": "Garbage collection triggered"}

# --------------------------------------------------------------------
# Telemetry helper
# --------------------------------------------------------------------
async def record_telemetry(query: str, response: str, tier: str, latency_ms: float, tokens: int):
    """Background task to record usage metrics (if telemetry enabled)."""
    try:
        from src.licensing.telemetry import TelemetryCollector
        telemetry = TelemetryCollector()
        telemetry.record_request(tier, endpoint="chat", latency_ms=latency_ms, tokens_generated=tokens)
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Telemetry failed: {e}")

# --------------------------------------------------------------------
# Root redirect
# --------------------------------------------------------------------
@router.get("/", include_in_schema=False)
async def root():
    return {"message": "CrownStar‑Absolute Enterprise API", "docs": "/docs"}

# ====================================================================================================
# END OF routes.py
# ====================================================================================================
