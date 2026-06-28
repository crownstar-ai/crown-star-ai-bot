# finetune/api.py – REST API for fine‑tuning jobs
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
from .service import get_finetune_service
from .data.dataset_utils import ConversationDatasetBuilder
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/finetune", tags=["Fine‑Tuning"])

class TrainRequest(BaseModel):
    base_model: str = "deepseek-ai/DeepSeek-V2-Lite"
    dataset_path: Optional[str] = None
    use_conversations: bool = False
    hyperparams: Optional[Dict] = None

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    base_model: str
    start_time: Optional[float]
    end_time: Optional[float]
    error: Optional[str]

@router.post("/train")
async def start_training(req: TrainRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    svc = get_finetune_service()
    dataset_path = req.dataset_path
    if req.use_conversations:
        builder = ConversationDatasetBuilder()
        dataset_path = builder.from_conversations()
    if not dataset_path:
        raise HTTPException(400, "Must provide dataset_path or set use_conversations=true")
    job_id = svc.submit_job(req.base_model, dataset_path, req.hyperparams)
    return {"job_id": job_id, "message": "Fine‑tuning job submitted"}

@router.get("/jobs")
async def list_jobs(limit: int = 20, user: dict = Depends(require_permission("admin"))):
    svc = get_finetune_service()
    jobs = svc.list_jobs(limit)
    return {"jobs": jobs}

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_finetune_service()
    status = svc.get_job_status(job_id)
    if not status:
        raise HTTPException(404, "Job not found")
    return status

@router.post("/datasets/export")
async def export_conversations(limit: int = 1000, user: dict = Depends(require_permission("admin"))):
    builder = ConversationDatasetBuilder()
    output = builder.from_conversations()
    return {"output_path": output, "message": "Conversations exported to JSONL"}

@router.get("/adapters")
async def list_adapters(user: dict = Depends(require_permission("user"))):
    import os
    adapters_dir = "data/finetune/adapters"
    if not os.path.exists(adapters_dir):
        return {"adapters": []}
    adapters = []
    for d in os.listdir(adapters_dir):
        path = os.path.join(adapters_dir, d)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "adapter_config.json")):
            adapters.append({"name": d, "path": path})
    return {"adapters": adapters}
