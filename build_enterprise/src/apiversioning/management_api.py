# apiversioning/management_api.py – Admin endpoints for version lifecycle
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from .version_registry import get_version_registry, VersionStatus

router = APIRouter(prefix="/v1/api-versioning", tags=["API Version Management"])

class DeprecateVersionRequest(BaseModel):
    version: str
    deprecation_date: date

class SunsetVersionRequest(BaseModel):
    version: str
    sunset_date: date

class SetDefaultVersionRequest(BaseModel):
    version: str

@router.get("/versions")
async def list_api_versions():
    registry = get_version_registry()
    versions = registry.list_versions()
    return {
        "versions": [
            {
                "version": v.version,
                "status": v.status.value,
                "introduced_at": v.introduced_at.isoformat(),
                "deprecated_at": v.deprecated_at.isoformat() if v.deprecated_at else None,
                "sunset_at": v.sunset_at.isoformat() if v.sunset_at else None,
                "base_path": v.base_path,
                "changelog_url": v.changelog_url
            } for v in versions
        ],
        "default_version": registry.default_version
    }

@router.post("/versions/deprecate")
async def deprecate_version(req: DeprecateVersionRequest):
    registry = get_version_registry()
    if not registry.get_version(req.version):
        raise HTTPException(404, f"Version {req.version} not found")
    registry.deprecate_version(req.version, req.deprecation_date)
    return {"message": f"Version {req.version} deprecated effective {req.deprecation_date}"}

@router.post("/versions/sunset")
async def sunset_version(req: SunsetVersionRequest):
    registry = get_version_registry()
    if not registry.get_version(req.version):
        raise HTTPException(404, f"Version {req.version} not found")
    registry.sunset_version(req.version, req.sunset_date)
    return {"message": f"Version {req.version} sunset effective {req.sunset_date}"}

@router.post("/versions/default")
async def set_default_version(req: SetDefaultVersionRequest):
    registry = get_version_registry()
    if not registry.get_version(req.version):
        raise HTTPException(404, f"Version {req.version} not found")
    registry.default_version = req.version
    registry.save()
    return {"default_version": req.version}

@router.get("/docs/{version}")
async def get_version_docs(version: str):
    """Redirect to version‑specific OpenAPI documentation"""
    # In real implementation, serve OpenAPI JSON for that version
    return {"message": f"Documentation for version {version} would be served here"}
