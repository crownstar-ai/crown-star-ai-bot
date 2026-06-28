# caching/api.py – Cache management endpoints
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from .cache_service import get_cache
from .cdn import get_cdn
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/cache", tags=["Cache"])

class PurgeRequest(BaseModel):
    urls: List[str]
    pattern: Optional[str] = None

@router.get("/stats")
async def cache_stats(user: dict = Depends(require_permission("analytics:view"))):
    cache = get_cache()
    stats = cache.get_stats()
    return stats

@router.post("/clear")
async def clear_cache(user: dict = Depends(require_permission("admin"))):
    cache = get_cache()
    cache.clear()
    return {"message": "Cache cleared"}

@router.post("/invalidate")
async def invalidate(req: PurgeRequest, user: dict = Depends(require_permission("admin"))):
    cache = get_cache()
    if req.pattern:
        cache.invalidate_pattern(req.pattern)
        return {"message": f"Invalidated pattern: {req.pattern}"}
    elif req.urls:
        for url in req.urls:
            # Parse URL to extract cache key
            cache.invalidate("http", url)
        # Also purge CDN
        cdn = get_cdn()
        if req.urls:
            cdn.purge_urls(req.urls)
        return {"message": f"Invalidated {len(req.urls)} URLs and purged CDN"}
    raise HTTPException(400, "Provide either urls or pattern")

@router.post("/warm")
async def warm_cache(pattern: str, user: dict = Depends(require_permission("admin"))):
    """Pre‑warm cache for URLs matching pattern (simulated)"""
    # In production, this would trigger a background task to fetch URLs
    return {"message": f"Cache warming initiated for pattern: {pattern}", "status": "background"}
