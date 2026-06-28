# chaos/api.py – REST API for chaos experiments
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from .service import get_chaos_engine
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/chaos", tags=["Chaos Engineering"])

class InjectRequest(BaseModel):
    type: str  # latency, error, memory, cpu, network, pod_kill
    target: str = "api"
    duration: Optional[int] = 30
    intensity: float = 0.5

@router.post("/inject")
async def inject_fault(req: InjectRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    engine = get_chaos_engine()
    if engine.is_safe_mode():
        raise HTTPException(403, "Chaos engineering is in safe mode. Set safe_mode=false to enable.")
    try:
        exp_id = engine.start_experiment(req.type, req.target, req.duration, req.intensity)
        return {"experiment_id": exp_id, "message": f"Started {req.type} chaos experiment for {req.duration}s"}
    except Exception as e:
        raise HTTPException(400, str(e))

@router.post("/stop/{exp_id}")
async def stop_experiment(exp_id: str, user: dict = Depends(require_permission("admin"))):
    engine = get_chaos_engine()
    if engine.stop_experiment(exp_id):
        return {"message": f"Experiment {exp_id} stopped"}
    raise HTTPException(404, "Experiment not found")

@router.post("/stop/all")
async def stop_all(user: dict = Depends(require_permission("admin"))):
    engine = get_chaos_engine()
    engine.stop_all_experiments()
    return {"message": "All chaos experiments stopped"}

@router.get("/status")
async def chaos_status(user: dict = Depends(require_permission("admin"))):
    engine = get_chaos_engine()
    return engine.get_status()

@router.post("/safemode")
async def set_safe_mode(enabled: bool, user: dict = Depends(require_permission("admin"))):
    engine = get_chaos_engine()
    engine.set_safe_mode(enabled)
    return {"safe_mode": enabled}

@router.get("/scenarios")
async def list_scenarios(user: dict = Depends(require_permission("user"))):
    return {
        "scenarios": [
            {"name": "high_latency", "type": "latency", "description": "Adds 50-5000ms delay to API calls"},
            {"name": "error_flood", "type": "error", "description": "Inject 10-50% error rate"},
            {"name": "memory_leak", "type": "memory", "description": "Consume memory gradually"},
            {"name": "cpu_spike", "type": "cpu", "description": "CPU load to 100% on one core"},
            {"name": "network_partition", "type": "network", "description": "Block egress to subnet"},
            {"name": "pod_kill", "type": "pod_kill", "description": "Terminate Kubernetes pod"}
        ]
    }
