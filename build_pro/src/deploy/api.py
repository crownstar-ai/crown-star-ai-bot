# deploy/api.py – REST API for deployment orchestration
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from .orchestrator.orchestrator import get_orchestrator, CloudProvider, DeploymentStrategy
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/deploy", tags=["Deployment"])

class CreateEnvironmentRequest(BaseModel):
    name: str
    provider: str  # aws, azure, gcp, sovereign_au
    region: str
    infrastructure_code_path: Optional[str] = None

class DeployRequest(BaseModel):
    environment_id: str
    version: str
    strategy: Optional[str] = None  # blue_green, canary, rolling, recreate

class FailoverRequest(BaseModel):
    from_environment_id: str
    to_environment_id: str

@router.post("/environment")
async def create_environment(req: CreateEnvironmentRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    orch = get_orchestrator()
    provider = CloudProvider(req.provider)
    env = orch.create_environment(req.name, provider, req.region, req.infrastructure_code_path)
    return {"environment_id": env.env_id, "name": env.name, "provider": req.provider, "region": req.region}

@router.get("/environments")
async def list_environments(user=Depends(require_permission("admin"))):
    orch = get_orchestrator()
    return {"environments": orch.list_environments()}

@router.post("/deploy")
async def deploy(req: DeployRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    orch = get_orchestrator()
    strategy = DeploymentStrategy(req.strategy) if req.strategy else None
    deployment = orch.deploy(req.environment_id, req.version, strategy)
    return {"deployment_id": deployment.deployment_id, "status": deployment.status, "strategy": deployment.strategy.value}

@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str, user=Depends(require_permission("admin"))):
    orch = get_orchestrator()
    status = orch.get_deployment_status(deployment_id)
    if "error" in status:
        raise HTTPException(404, "Deployment not found")
    return status

@router.post("/failover")
async def failover(req: FailoverRequest, user=Depends(require_permission("admin"))):
    orch = get_orchestrator()
    success = orch.failover(req.from_environment_id, req.to_environment_id)
    if not success:
        raise HTTPException(400, "Failover failed - environments not found")
    return {"status": "failover initiated", "from": req.from_environment_id, "to": req.to_environment_id}
