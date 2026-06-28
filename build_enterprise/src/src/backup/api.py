# backup/api.py – REST API for backup management
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from .backup_service import get_backup_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/backup", tags=["Backup"])

class BackupRequest(BaseModel):
    backup_type: str = "full"

class RestoreRequest(BaseModel):
    backup_name: str
    restore_to_latest: bool = False

@router.post("/create")
async def create_backup(req: BackupRequest, user: dict = Depends(require_permission("admin")), background: BackgroundTasks = None):
    service = get_backup_service()
    if background:
        background.add_task(service.create_backup, req.backup_type)
        return {"message": "Backup started in background"}
    else:
        result = service.create_backup(req.backup_type)
        return {"message": "Backup created", "backup": result}

@router.get("/list")
async def list_backups(user: dict = Depends(require_permission("admin"))):
    service = get_backup_service()
    backups = service.list_backups()
    return {"backups": backups}

@router.post("/restore")
async def restore_backup(req: RestoreRequest, user: dict = Depends(require_permission("admin"))):
    service = get_backup_service()
    try:
        if req.restore_to_latest:
            success = service.restore_backup("", restore_to="latest")
        else:
            success = service.restore_backup(req.backup_name)
        if success:
            return {"message": "Restore completed successfully"}
        else:
            raise HTTPException(404, "Backup not found")
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/verify")
async def verify_backups(user: dict = Depends(require_permission("admin"))):
    service = get_backup_service()
    result = service.verify_backups()
    return result

@router.get("/config")
async def get_backup_config(user: dict = Depends(require_permission("admin"))):
    service = get_backup_service()
    return service.config

@router.post("/config")
async def update_backup_config(config: dict, user: dict = Depends(require_permission("admin"))):
    service = get_backup_service()
    service.config.update(config)
    service.save_config()
    return {"message": "Config updated"}
