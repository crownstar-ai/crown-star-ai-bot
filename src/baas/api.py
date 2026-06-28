# baas/api.py – REST API for Backup as a Service
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from .service import get_baas_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/baas", tags=["Backup as a Service"])

class CreateBackupRequest(BaseModel):
    source_path: str
    description: str = ""
    retention_days: int = 30

class RestoreBackupRequest(BaseModel):
    backup_id: str
    target_path: Optional[str] = None
    overwrite: bool = False

@router.post("/backup")
async def create_backup(req: CreateBackupRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    # Run in background
    def do_backup():
        svc.create_backup(req.source_path, req.description, req.retention_days)
    background.add_task(do_backup)
    return {"message": "Backup started", "source": req.source_path, "retention_days": req.retention_days}

@router.get("/backups")
async def list_backups(source: Optional[str] = None, user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    backups = svc.list_backups(source)
    return {"backups": [{"id": b.backup_id, "created_at": b.created_at.isoformat(), "size_bytes": b.size_bytes, "source": b.source, "status": b.status} for b in backups]}

@router.get("/backup/{backup_id}")
async def get_backup(backup_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    backup = svc.get_backup_details(backup_id)
    if not backup:
        raise HTTPException(404, "Backup not found")
    return {"backup_id": backup.backup_id, "created_at": backup.created_at.isoformat(), "size_bytes": backup.size_bytes, "source": backup.source, "status": backup.status}

@router.post("/restore")
async def restore_backup(req: RestoreBackupRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    def do_restore():
        svc.restore_backup(req.backup_id, req.target_path, overwrite=req.overwrite)
    background.add_task(do_restore)
    return {"message": "Restore started", "backup_id": req.backup_id}

@router.delete("/backup/{backup_id}")
async def delete_backup(backup_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    if svc.delete_backup(backup_id):
        return {"message": f"Backup {backup_id} deleted"}
    raise HTTPException(404, "Backup not found")

@router.post("/verify/{backup_id}")
async def verify_backup(backup_id: str, user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    valid = svc.verify_backup(backup_id)
    return {"backup_id": backup_id, "valid": valid}

@router.get("/status")
async def baas_status(user: dict = Depends(require_permission("admin"))):
    svc = get_baas_service()
    return svc.get_status()

@router.get("/providers")
async def list_providers(user: dict = Depends(require_permission("admin"))):
    return {"providers": ["local", "aws", "azure", "gcp", "veeam", "commvault"], "active": get_baas_service().config["provider"]}
