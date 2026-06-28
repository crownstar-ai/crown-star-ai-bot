# chaos/platform/api.py – REST API for chaos engineering platform
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from .orchestrator.orchestrator import get_chaos_orchestrator
from .chaos_mesh.client import get_chaos_mesh_client
from .gremlin.client import get_gremlin_client
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/chaos/platform", tags=["Chaos Platform"])

class RunScenarioRequest(BaseModel):
    provider: str = "chaos_mesh"  # chaos_mesh, gremlin
    scenario_type: str  # pod_kill, pod_failure, network_latency, network_loss, cpu_stress, memory_stress, cpu, memory, latency, shutdown
    target: Dict
    duration_seconds: int = 60
    parameters: Optional[Dict] = None

@router.post("/scenario/run")
async def run_scenario(req: RunScenarioRequest, user: dict = Depends(require_permission("admin"))):
    orch = get_chaos_orchestrator()
    result = orch.run_scenario(req.provider, req.scenario_type, req.target, req.duration_seconds, req.parameters)
    return result

@router.get("/experiments")
async def list_experiments(limit: int = 20, user: dict = Depends(require_permission("admin"))):
    orch = get_chaos_orchestrator()
    exps = orch.list_experiments(limit)
    return {"experiments": exps}

@router.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str, user: dict = Depends(require_permission("admin"))):
    orch = get_chaos_orchestrator()
    exp = orch.get_status(exp_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    return exp

@router.post("/experiments/{exp_id}/stop")
async def stop_experiment(exp_id: str, user: dict = Depends(require_permission("admin"))):
    orch = get_chaos_orchestrator()
    if orch.stop_experiment(exp_id):
        return {"message": f"Experiment {exp_id} stopped"}
    raise HTTPException(404, "Experiment not found or cannot stop")

@router.get("/providers")
async def list_providers(user: dict = Depends(require_permission("admin"))):
    return {"providers": ["chaos_mesh", "gremlin"], "default": "chaos_mesh"}

@router.get("/gremlin/scenarios")
async def list_gremlin_scenarios(user: dict = Depends(require_permission("admin"))):
    gremlin = get_gremlin_client()
    scenarios = gremlin.list_scenarios()
    return {"scenarios": scenarios}

@router.get("/chaos-mesh/chaos")
async def list_chaos_mesh_chaos(kind: str = "podchaos", user: dict = Depends(require_permission("admin"))):
    client = get_chaos_mesh_client()
    items = client.list_chaos(kind)
    return {kind: items}
