# batch/api.py – REST API for batch jobs
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from .batch_service import get_batch_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/batch", tags=["Batch Processing"])

class SubmitJobRequest(BaseModel):
    name: str
    job_type: str  # analytics, backup, training, report, custom
    parameters: Optional[Dict] = None
    command: Optional[List[str]] = None
    environment: Optional[Dict] = None

@router.post("/submit")
async def submit_job(req: SubmitJobRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_batch_service()
    if req.job_type == "custom":
        if not req.command:
            raise HTTPException(400, "command required for custom job")
        job_id = svc.submit_custom(req.name, req.command, req.environment)
    else:
        job_id = svc.submit_job(req.name, req.job_type, req.parameters)
    return {"job_id": job_id, "message": "Job submitted"}

@router.get("/jobs")
async def list_jobs(limit: int = 50, user: dict = Depends(require_permission("admin"))):
    svc = get_batch_service()
    jobs = svc.list_jobs(limit)
    return {"jobs": [{"job_id": j.job_id, "name": j.name, "status": j.status, "created_at": j.created_at.isoformat()} for j in jobs]}

@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_batch_service()
    job = svc.get_job_status(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"job_id": job.job_id, "name": job.name, "status": job.status, "created_at": job.created_at.isoformat(), "started_at": job.started_at.isoformat() if job.started_at else None, "completed_at": job.completed_at.isoformat() if job.completed_at else None}

@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str, tail_lines: int = 100, user: dict = Depends(require_permission("admin"))):
    svc = get_batch_service()
    logs = svc.get_job_logs(job_id, tail_lines)
    return {"job_id": job_id, "logs": logs}

@router.delete("/jobs/{job_id}")
async def terminate_job(job_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_batch_service()
    if svc.terminate_job(job_id):
        return {"message": f"Job {job_id} terminated"}
    raise HTTPException(404, "Job not found or cannot terminate")
