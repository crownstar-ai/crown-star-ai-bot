# secrets/api.py – REST API for secret CRUD
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from .service import get_secrets
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/secrets", tags=["Secrets Management"])

class SecretSetRequest(BaseModel):
    value: str
    metadata: Optional[dict] = None

class SecretResponse(BaseModel):
    key: str
    value: Optional[str] = None
    version: Optional[str] = None

@router.get("/{key}")
async def get_secret(key: str, version: str = "latest", user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    value = svc.get(key, version)
    if value is None:
        raise HTTPException(404, "Secret not found")
    return SecretResponse(key=key, value=value, version=version)

@router.post("/{key}")
async def set_secret(key: str, req: SecretSetRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    if svc.set(key, req.value, req.metadata):
        return {"message": f"Secret {key} saved"}
    raise HTTPException(500, "Failed to save secret")

@router.delete("/{key}")
async def delete_secret(key: str, user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    if svc.delete(key):
        return {"message": f"Secret {key} deleted"}
    raise HTTPException(404, "Secret not found")

@router.post("/{key}/rotate")
async def rotate_secret(key: str, new_value: Optional[str] = None, user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    new_val = svc.rotate(key, new_value)
    if new_val:
        return {"message": f"Secret {key} rotated", "new_value": new_val}
    raise HTTPException(404, "Secret not found or rotation failed")

@router.get("/")
async def list_secrets(prefix: str = "", user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    keys = svc.list_keys(prefix)
    return {"keys": keys}

@router.get("/metadata/{key}")
async def secret_metadata(key: str, user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    meta = svc.get_metadata(key)
    if not meta:
        raise HTTPException(404, "Secret not found")
    return {"key": meta.key, "version": meta.version, "created_at": meta.created_at.isoformat(), "updated_at": meta.updated_at.isoformat(), "metadata": meta.metadata}

@router.get("/providers")
async def list_providers(user: dict = Depends(require_permission("admin"))):
    return {"providers": ["local", "hashicorp_vault", "aws", "azure", "gcp"], "active": get_secrets().config["provider"]}

@router.get("/status")
async def secrets_status(user: dict = Depends(require_permission("admin"))):
    svc = get_secrets()
    return {"provider": svc.config["provider"], "cache_size": len(svc.cache), "rotation_enabled": svc.config["rotation"]["enabled"]}
