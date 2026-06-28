# flags/api.py – REST API for feature flags
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_flags_manager, FlagDefinition, FlagType, FlagKind, RolloutStrategy, EvaluationContext
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/features", tags=["Feature Flags & A/B Testing"])

class FlagCreateRequest(BaseModel):
    key: str; name: str; flag_type: str; kind: str = "feature_flag"; default_value: Any
    enabled: bool = True; rollout_strategy: str = "hash"; rules: Optional[List] = None
    variants: Optional[Dict] = None; rollout_percentage: float = 100.0; description: str = ""

class EvaluateRequest(BaseModel):
    key: str; user_id: str; email: Optional[str] = None
    country: Optional[str] = None; tier: Optional[str] = None; custom: Optional[Dict] = None

class TrackConversionRequest(BaseModel):
    experiment_key: str; user_id: str; event_name: str

@router.post("/flags")
async def create_flag(req: FlagCreateRequest, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    flag = FlagDefinition(key=req.key, name=req.name, flag_type=FlagType(req.flag_type), kind=FlagKind(req.kind), default_value=req.default_value, enabled=req.enabled, rollout_strategy=RolloutStrategy(req.rollout_strategy), rules=req.rules, variants=req.variants, rollout_percentage=req.rollout_percentage, description=req.description)
    mgr.create_flag(flag)
    return {"key": req.key, "status": "created"}

@router.put("/flags/{key}")
async def update_flag(key: str, req: FlagCreateRequest, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    existing = mgr.get_flag(key)
    if not existing: raise HTTPException(404, "Flag not found")
    flag = FlagDefinition(key=key, name=req.name, flag_type=FlagType(req.flag_type), kind=FlagKind(req.kind), default_value=req.default_value, enabled=req.enabled, rollout_strategy=RolloutStrategy(req.rollout_strategy), rules=req.rules, variants=req.variants, rollout_percentage=req.rollout_percentage, description=req.description)
    mgr.update_flag(flag)
    return {"key": key, "status": "updated"}

@router.delete("/flags/{key}")
async def delete_flag(key: str, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    success = mgr.delete_flag(key)
    if not success: raise HTTPException(404, "Flag not found")
    return {"key": key, "status": "deleted"}

@router.get("/flags")
async def list_flags(user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    return {"flags": [asdict(f) for f in mgr.list_flags()]}

@router.post("/evaluate")
async def evaluate_flag(req: EvaluateRequest, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    context = EvaluationContext(user_id=req.user_id, email=req.email, country=req.country, tier=req.tier, custom=req.custom)
    result = mgr.evaluate(req.key, context)
    return {"flag": req.key, "value": result.value, "variant": result.variant, "reason": result.reason}

@router.post("/track")
async def track_conversion(req: TrackConversionRequest, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    mgr.track_conversion(req.experiment_key, req.user_id, req.event_name)
    return {"status": "tracked"}

@router.get("/experiments/{key}/results")
async def get_experiment_results(key: str, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    results = mgr.get_experiment_results(key)
    return {"experiment": key, "results": results}

@router.get("/audit")
async def get_audit_log(limit: int = 100, user=Depends(require_permission("admin"))):
    mgr = get_flags_manager()
    log = mgr.get_audit_log(limit)
    return {"audit": log}
