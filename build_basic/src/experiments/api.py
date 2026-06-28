# experiments/api.py – REST endpoints for A/B testing and feature flags
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, List
from .service import get_exp_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/experiments", tags=["Experiments"])

class CreateExperimentRequest(BaseModel):
    name: str
    variants: Dict[str, int]  # e.g., {"control": 50, "variant_a": 50}
    target_metric: str = "conversion"
    min_sample_size: int = 1000

class AssignRequest(BaseModel):
    experiment_id: str
    user_id: str

class TrackEventRequest(BaseModel):
    experiment_id: str
    user_id: str
    event_type: str
    value: float = 1.0

class FeatureFlagRequest(BaseModel):
    key: str
    enabled: bool
    rollout_percentage: int = 100
    description: str = ""

@router.post("/create")
async def create_experiment(req: CreateExperimentRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_exp_service()
    exp_id = svc.create_experiment(req.name, req.variants, req.target_metric, req.min_sample_size)
    return {"experiment_id": exp_id, "name": req.name}

@router.post("/start/{exp_id}")
async def start_experiment(exp_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_exp_service()
    svc.start_experiment(exp_id)
    return {"message": f"Experiment {exp_id} started"}

@router.post("/stop/{exp_id}")
async def stop_experiment(exp_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_exp_service()
    svc.stop_experiment(exp_id)
    return {"message": f"Experiment {exp_id} stopped"}

@router.post("/assign")
async def assign_variant(req: AssignRequest, user: dict = Depends(require_permission("user"))):
    svc = get_exp_service()
    variant = svc.assign_variant(req.experiment_id, req.user_id)
    if variant is None:
        raise HTTPException(404, "Experiment not found")
    return {"variant": variant}

@router.post("/track")
async def track_event(req: TrackEventRequest, user: dict = Depends(require_permission("user"))):
    svc = get_exp_service()
    svc.track_event(req.experiment_id, req.user_id, req.event_type, req.value)
    return {"status": "tracked"}

@router.get("/results/{exp_id}")
async def get_results(exp_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_exp_service()
    results = svc.get_results(exp_id)
    return results

@router.get("/list")
async def list_experiments(user: dict = Depends(require_permission("admin"))):
    svc = get_exp_service()
    cursor = svc.conn.execute("SELECT id, name, status, start_time, end_time FROM experiments")
    exps = [{"id": r[0], "name": r[1], "status": r[2], "start_time": r[3], "end_time": r[4]} for r in cursor.fetchall()]
    return {"experiments": exps}

# Feature flags endpoints
@router.get("/features")
async def list_features(user: dict = Depends(require_permission("user"))):
    svc = get_exp_service()
    features = svc.list_feature_flags()
    return {"features": features}

@router.post("/features")
async def set_feature_flag(req: FeatureFlagRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_exp_service()
    svc.set_feature_flag(req.key, req.enabled, req.rollout_percentage, req.description)
    return {"message": f"Feature flag {req.key} updated"}

@router.get("/features/{key}")
async def get_feature_flag(key: str, user_id: Optional[str] = None, user: dict = Depends(require_permission("user"))):
    svc = get_exp_service()
    enabled = svc.is_feature_enabled(key, user_id)
    return {"key": key, "enabled": enabled}
