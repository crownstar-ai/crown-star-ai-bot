# rlhf/api.py – REST API for RLHF pipeline
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
from .core import get_rlhf_manager, PreferencePair
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/rlhf", tags=["RLHF"])

class PreferenceSubmit(BaseModel):
    prompt: str
    response_a: str
    response_b: str
    preferred: str  # "a", "b", "tie"
    annotator_id: str = "human"
    metadata: Optional[Dict] = None

class RewardTrainRequest(BaseModel):
    epochs: Optional[int] = None

class PolicyTrainRequest(BaseModel):
    base_model_path: str
    output_path: str
    method: str = "dpo"  # dpo, ppo

@router.post("/preference")
async def submit_preference(req: PreferenceSubmit, user=Depends(require_permission("admin"))):
    """Submit a human preference between two model responses."""
    mgr = get_rlhf_manager()
    pref_id = mgr.add_preference(
        prompt=req.prompt,
        response_a=req.response_a,
        response_b=req.response_b,
        preferred=req.preferred,
        annotator_id=req.annotator_id,
        metadata=req.metadata
    )
    return {"preference_id": pref_id, "status": "recorded"}

@router.get("/preferences")
async def list_preferences(limit: int = 100, user=Depends(require_permission("admin"))):
    """List collected preferences."""
    mgr = get_rlhf_manager()
    prefs = mgr.preferences[-limit:]
    return {"preferences": [asdict(p) for p in prefs]}

@router.post("/train/reward")
async def train_reward_model(req: RewardTrainRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Train the reward model on collected preferences."""
    mgr = get_rlhf_manager()
    result = mgr.train_reward_model()
    return result

@router.post("/train/policy")
async def train_policy(req: PolicyTrainRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Fine‑tune policy using RLHF (DPO/PPO)."""
    mgr = get_rlhf_manager()
    result = mgr.train_policy(req.base_model_path, req.output_path)
    return result

@router.get("/evaluate/reward")
async def evaluate_reward_model(user=Depends(require_permission("admin"))):
    """Evaluate reward model accuracy on held‑out preferences."""
    mgr = get_rlhf_manager()
    # In real, would split preferences
    result = mgr.evaluate_reward_model([])
    return result

@router.get("/stats")
async def rlhf_stats(user=Depends(require_permission("admin"))):
    """Get RLHF pipeline statistics."""
    mgr = get_rlhf_manager()
    return mgr.get_statistics()
