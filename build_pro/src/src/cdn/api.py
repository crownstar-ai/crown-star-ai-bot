# cdn/api.py – REST API for CDN and edge caching
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from .manager import get_cdn_manager, CDNManager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/cdn", tags=["CDN & Edge"])

class PurgeRequest(BaseModel):
    paths: List[str]
    provider: Optional[str] = None
    all_providers: bool = False

class PrefetchRequest(BaseModel):
    urls: List[str]
    provider: Optional[str] = None

class GeoRestrictionRequest(BaseModel):
    country_codes: List[str]   # e.g., ["AU", "NZ", "US"]
    provider: Optional[str] = None

@router.post("/purge")
async def purge_cdn(req: PurgeRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Purge cached paths from CDN."""
    cdn = get_cdn_manager()
    results = cdn.purge_paths(req.paths, req.provider, req.all_providers)
    return {"results": [r.__dict__ for r in results]}

@router.post("/invalidate/{path:path}")
async def invalidate_path(path: str, provider: Optional[str] = None, user=Depends(require_permission("admin"))):
    """Invalidate a single path (shortcut)."""
    cdn = get_cdn_manager()
    result = cdn.invalidate_path(path, provider)
    return result

@router.post("/prefetch")
async def prefetch_assets(req: PrefetchRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Warm CDN cache by prefetching asset URLs."""
    cdn = get_cdn_manager()
    result = cdn.prefetch_assets(req.urls, req.provider)
    return {"prefetch_results": result}

@router.get("/status")
async def cdn_status(provider: Optional[str] = None, user=Depends(require_permission("admin"))):
    """Get CDN provider health and statistics."""
    cdn = get_cdn_manager()
    return cdn.get_cdn_status(provider)

@router.post("/geo")
async def apply_geo_restrictions(req: GeoRestrictionRequest, user=Depends(require_permission("admin"))):
    """Apply geo‑restriction rules to CDN (e.g., only AU/NZ)."""
    cdn = get_cdn_manager()
    result = cdn.apply_geo_restrictions(req.country_codes, req.provider)
    return {"geo_rules_updated": result}

@router.get("/rules")
async def list_cache_rules(user=Depends(require_permission("admin"))):
    """List active cache rules."""
    cdn = get_cdn_manager()
    return {"rules": [{"path": r.path_pattern, "ttl": r.ttl_seconds, "edge_ttl": r.edge_ttl_seconds} for r in cdn.rules]}
