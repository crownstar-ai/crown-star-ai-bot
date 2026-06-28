# tracing/api.py – REST API for distributed tracing
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from dataclasses import asdict
from .core import get_obs_manager, SpanKind, SpanStatus
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/tracing", tags=["Observability & Tracing"])

class SamplingUpdateRequest(BaseModel):
    strategy: str
    param: float

@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, user=Depends(require_permission("admin"))):
    mgr = get_obs_manager()
    trace = mgr.get_trace(trace_id)
    if not trace: raise HTTPException(404, "Trace not found")
    return {"trace": asdict(trace)}

@router.get("/spans")
async def query_spans(service: Optional[str] = None, operation: Optional[str] = None,
                      start_time: Optional[int] = None, end_time: Optional[int] = None,
                      limit: int = 100, user=Depends(require_permission("admin"))):
    mgr = get_obs_manager()
    spans = mgr.query_spans(service=service, operation=operation, start_time=start_time, end_time=end_time, limit=limit)
    return {"spans": [asdict(s) for s in spans]}

@router.post("/sampling")
async def update_sampling(req: SamplingUpdateRequest, user=Depends(require_permission("admin"))):
    mgr = get_obs_manager()
    mgr.update_sampling(req.strategy, req.param)
    return {"status": "updated", "strategy": req.strategy, "param": req.param}

@router.get("/sampling")
async def get_sampling(user=Depends(require_permission("admin"))):
    mgr = get_obs_manager()
    return {"strategy": mgr.config["sampling"]["strategy"], "param": mgr.config["sampling"]["param"]}

@router.get("/stats")
async def trace_stats(user=Depends(require_permission("admin"))):
    mgr = get_obs_manager()
    return mgr.get_stats()
