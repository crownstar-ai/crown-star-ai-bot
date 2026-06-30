# src/api/routes/system.py
"""
System management endpoints: health, version, status.
"""

import os
import sys
import time
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

from src.core.version import VERSION, APP_VERSION
from src.core.logging_config import get_logger
from src.core.health import HealthChecker

router = APIRouter()
logger = get_logger(__name__)

health_checker = HealthChecker()


@router.get("/health")
async def health(request: Request):
    """Comprehensive health check."""
    result = health_checker.check_all()
    status_code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(status_code=status_code, content=result)


@router.get("/version")
async def version(request: Request):
    """Get version information."""
    return {
        "version": APP_VERSION,
        "build_date": VERSION.build_date,
        "build_timestamp": VERSION.build_timestamp,
        "python": sys.version,
        "platform": sys.platform,
    }


@router.get("/status")
async def status(request: Request):
    """Get system status (uptime, memory, etc.)."""
    import psutil
    process = psutil.Process()
    return {
        "uptime_seconds": time.time() - process.create_time(),
        "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
        "cpu_percent": process.cpu_percent(),
        "connections": len(process.connections()),
        "threads": process.num_threads(),
    }


@router.post("/reload")
async def reload_config(request: Request):
    """Reload configuration (Enterprise only)."""
    tier = getattr(request.state, "tier", "free")
    if tier != "enterprise":
        return JSONResponse(status_code=403, content={"error": "Enterprise tier required"})
    
    # Reload settings
    from src.core.config import reload_settings
    reload_settings()
    logger.info("Configuration reloaded")
    return {"status": "reloaded"}


@router.post("/backup")
async def trigger_backup(request: Request):
    """Trigger a backup (Enterprise only)."""
    tier = getattr(request.state, "tier", "free")
    if tier != "enterprise":
        return JSONResponse(status_code=403, content={"error": "Enterprise tier required"})
    
    # In production, would trigger async backup
    logger.info("Backup triggered")
    return {"status": "backup_started"}
