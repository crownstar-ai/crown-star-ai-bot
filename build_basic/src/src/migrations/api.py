# src/migrations/api.py – REST API for database migrations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from .migration_service import get_migration_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/migrations", tags=["Database Migrations"])

class RollbackRequest(BaseModel):
    steps: int = 1

@router.get("/status")
async def migration_status(user: dict = Depends(require_permission("admin"))):
    svc = get_migration_service()
    current = svc.get_current_version()
    history = svc.history(10)
    return {"current_version": current, "history": history, "engine": svc.engine}

@router.post("/upgrade")
async def migrate_upgrade(user: dict = Depends(require_permission("admin"))):
    svc = get_migration_service()
    success = svc.migrate()
    if success:
        return {"message": "Migration completed successfully"}
    raise HTTPException(500, "Migration failed")

@router.post("/downgrade")
async def migrate_downgrade(req: RollbackRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_migration_service()
    success = svc.rollback(req.steps)
    if success:
        return {"message": f"Rolled back {req.steps} step(s)"}
    raise HTTPException(500, "Rollback failed")

@router.get("/history")
async def migration_history(limit: int = 20, user: dict = Depends(require_permission("admin"))):
    svc = get_migration_service()
    history = svc.history(limit)
    return {"history": history}
