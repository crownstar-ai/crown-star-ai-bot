# mlflow/api.py – REST API for MLflow tracking and model registry
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
from .service import get_mlflow_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/mlflow", tags=["MLflow"])

class RegisterModelRequest(BaseModel):
    local_path: str
    model_name: str
    description: Optional[str] = None

class PromoteModelRequest(BaseModel):
    model_name: str
    version: int
    stage: str  # Staging, Production, Archived

class LoadModelRequest(BaseModel):
    model_name: str
    stage: Optional[str] = "Production"
    version: Optional[int] = None

@router.get("/experiments")
async def list_experiments(user: dict = Depends(require_permission("user"))):
    svc = get_mlflow_service()
    exp = svc.client.search_experiments()
    return {"experiments": [{"id": e.experiment_id, "name": e.name, "lifecycle_stage": e.lifecycle_stage} for e in exp]}

@router.post("/experiments/create")
async def create_experiment(name: str, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    exp_id = svc.get_or_create_experiment(name)
    return {"experiment_id": exp_id}

@router.get("/runs")
async def search_runs(experiment_id: Optional[str] = None, filter_string: Optional[str] = None, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    exp_ids = [experiment_id] if experiment_id else [svc.get_or_create_experiment()]
    runs = svc.search_runs(exp_ids, filter_string)
    return {"runs": runs}

@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    run = svc.get_run(run_id)
    return run

@router.post("/model/register")
async def register_model(req: RegisterModelRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    result = svc.register_model(req.local_path, req.model_name, req.description)
    return result

@router.post("/model/register-from-run")
async def register_from_run(run_id: str, model_name: str, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    result = svc.register_model_from_run(run_id, model_name)
    return result

@router.post("/model/promote")
async def promote_model(req: PromoteModelRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    result = svc.promote_model_version(req.model_name, req.version, req.stage)
    return result

@router.get("/models")
async def list_models(user: dict = Depends(require_permission("user"))):
    svc = get_mlflow_service()
    models = svc.list_models()
    return {"models": models}

@router.get("/models/{model_name}/versions")
async def get_model_versions(model_name: str, user: dict = Depends(require_permission("user"))):
    svc = get_mlflow_service()
    versions = svc.get_model_versions(model_name)
    return {"versions": versions}

@router.post("/model/load")
async def load_model(req: LoadModelRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_mlflow_service()
    try:
        model = svc.load_model(req.model_name, req.stage, req.version)
        # Can't return model object, just metadata
        return {"model_name": req.model_name, "stage": req.stage, "version": req.version, "loaded": True}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/model/production/{model_name}")
async def get_production_model(model_name: str, user: dict = Depends(require_permission("user"))):
    svc = get_mlflow_service()
    model = svc.get_production_model(model_name)
    if not model:
        raise HTTPException(404, "No production model found")
    return model
