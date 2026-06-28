# scheduler/api.py – REST API for job management
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from .apscheduler_service import get_scheduler
from .celery.app import app as celery_app
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/scheduler", tags=["Scheduler"])

class AddJobRequest(BaseModel):
    job_id: str
    func_name: str
    trigger_type: str  # cron, interval, date
    cron: Optional[Dict] = None
    interval: Optional[Dict] = None
    run_date: Optional[str] = None

class TriggerJobRequest(BaseModel):
    job_id: str

@router.get("/jobs")
async def list_jobs(user: dict = Depends(require_permission("admin"))):
    sched = get_scheduler()
    jobs = sched.list_jobs()
    return {"jobs": jobs}

@router.post("/jobs")
async def add_job(req: AddJobRequest, user: dict = Depends(require_permission("admin"))):
    sched = get_scheduler()
    params = {}
    if req.cron:
        params.update(req.cron)
    if req.interval:
        params.update(req.interval)
    if req.run_date:
        params["run_date"] = req.run_date
    try:
        sched.add_job(req.job_id, req.func_name, req.trigger_type, **params)
        return {"message": f"Job {req.job_id} added"}
    except Exception as e:
        raise HTTPException(400, str(e))

@router.delete("/jobs/{job_id}")
async def remove_job(job_id: str, user: dict = Depends(require_permission("admin"))):
    sched = get_scheduler()
    if sched.remove_job(job_id):
        return {"message": f"Job {job_id} removed"}
    raise HTTPException(404, "Job not found")

@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str, user: dict = Depends(require_permission("admin"))):
    sched = get_scheduler()
    if sched.pause_job(job_id):
        return {"message": f"Job {job_id} paused"}
    raise HTTPException(404, "Job not found")

@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str, user: dict = Depends(require_permission("admin"))):
    sched = get_scheduler()
    if sched.resume_job(job_id):
        return {"message": f"Job {job_id} resumed"}
    raise HTTPException(404, "Job not found")

@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str, user: dict = Depends(require_permission("admin"))):
    sched = get_scheduler()
    if sched.trigger_job(job_id):
        return {"message": f"Job {job_id} triggered"}
    raise HTTPException(404, "Job not found")

@router.get("/celery/status")
async def celery_status(user: dict = Depends(require_permission("admin"))):
    try:
        i = celery_app.control.inspect()
        stats = i.stats()
        active = i.active()
        return {"status": "online", "workers": len(stats or {}), "stats": stats, "active": active}
    except Exception as e:
        return {"status": "offline", "error": str(e)}
