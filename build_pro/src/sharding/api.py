# sharding/api.py – REST API for sharding status and management
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from .routing.router import get_shard_router
from .pool.connection_pool import get_shard_manager
from .strategies.strategies import get_strategy
from security.dependencies import require_permission
import json

router = APIRouter(prefix="/v1/sharding", tags=["Database Sharding"])

class ReshardRequest(BaseModel):
    new_strategy: Optional[str] = None
    new_total_shards: Optional[int] = None

class MoveDataRequest(BaseModel):
    source_shard: str
    target_shard: str
    keys: List[str]

@router.get("/status")
async def sharding_status(user: dict = Depends(require_permission("admin"))):
    router = get_shard_router()
    manager = get_shard_manager()
    status = {
        "strategy": router.config["strategy"],
        "total_shards": router.config["total_shards"],
        "shards": list(manager.shards.keys()),
        "replicas_per_shard": {sid: len(replicas) for sid, replicas in manager.replicas.items()}
    }
    return status

@router.get("/stats")
async def shard_stats(shard_id: Optional[str] = None, user: dict = Depends(require_permission("admin"))):
    # Return per‑shard statistics (e.g., row count, size)
    stats = {}
    # Simplified: would query each shard
    return {"stats": stats}

@router.post("/reshard")
async def reshard(req: ReshardRequest, user: dict = Depends(require_permission("admin"))):
    """Change sharding strategy or number of shards (data migration required)"""
    router = get_shard_router()
    # In real implementation, would trigger background migration
    if req.new_strategy:
        router.config["strategy"] = req.new_strategy
    if req.new_total_shards:
        router.config["total_shards"] = req.new_total_shards
    # Save config
    with open("config/sharding/sharding_config.json", "w") as f:
        json.dump(router.config, f, indent=2)
    return {"message": "Sharding configuration updated. Data migration not performed automatically."}

@router.post("/move")
async def move_data(req: MoveDataRequest, user: dict = Depends(require_permission("admin"))):
    """Move specific keys from one shard to another (for rebalancing)"""
    # Placeholder – would copy data and update mapping
    return {"message": f"Scheduled move of {len(req.keys)} keys from {req.source_shard} to {req.target_shard}"}

@router.get("/key/{shard_key}")
async def get_shard_for_key(shard_key: str, user: dict = Depends(require_permission("admin"))):
    router = get_shard_router()
    shard_id = router.get_shard_id(shard_key)
    return {"shard_key": shard_key, "shard_id": shard_id}
