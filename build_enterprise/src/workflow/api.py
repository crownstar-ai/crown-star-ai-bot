# workflow/api.py – REST API for workflow orchestration
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_workflow_engine, get_scheduler, TaskDefinition, WorkflowDefinition, TriggerType
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/workflows", tags=["Workflow Orchestration"])

class TaskDefRequest(BaseModel):
    task_id: str; name: str; function: str; dependencies: List[str] = []
    retries: int = 0; retry_delay_seconds: int = 60; timeout_seconds: int = 3600
    resources: Optional[Dict] = None; params: Optional[Dict] = None

class WorkflowDefRequest(BaseModel):
    workflow_id: str; name: str; tasks: List[TaskDefRequest]; schedule: Optional[str] = None
    trigger_type: Optional[str] = None; trigger_config: Optional[Dict] = None
    concurrency_limit: int = 1; tags: List[str] = []

class TriggerRequest(BaseModel):
    workflow_id: str; metadata: Optional[Dict] = None

@router.post("/definitions")
async def create_workflow(req: WorkflowDefRequest, user=Depends(require_permission("admin"))):
    engine = get_workflow_engine()
    tasks = [TaskDefinition(**t.dict()) for t in req.tasks]
    trigger = TriggerType(req.trigger_type) if req.trigger_type else None
    wf_def = WorkflowDefinition(workflow_id=req.workflow_id, name=req.name, tasks=tasks, schedule=req.schedule, trigger=trigger, trigger_config=req.trigger_config, concurrency_limit=req.concurrency_limit, tags=req.tags)
    engine.register_workflow(wf_def)
    if req.schedule: get_scheduler().add_cron(req.schedule, req.workflow_id, {})
    return {"workflow_id": req.workflow_id, "status": "registered"}

@router.post("/trigger")
async def trigger_workflow(req: TriggerRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    engine = get_workflow_engine()
    try:
        instance_id = engine.trigger_workflow(req.workflow_id, req.metadata)
        return {"instance_id": instance_id, "status": "started"}
    except ValueError as e: raise HTTPException(404, str(e))

@router.get("/instances/{instance_id}")
async def get_workflow_status(instance_id: str, user=Depends(require_permission("admin"))):
    engine = get_workflow_engine()
    status = engine.get_status(instance_id)
    if not status: raise HTTPException(404, "Instance not found")
    return status

@router.get("/definitions")
async def list_workflows(user=Depends(require_permission("admin"))):
    engine = get_workflow_engine()
    return {"workflows": engine.list_workflows()}

@router.get("/instances")
async def list_instances(workflow_id: Optional[str] = None, user=Depends(require_permission("admin"))):
    engine = get_workflow_engine()
    return {"instances": engine.list_instances(workflow_id)}
