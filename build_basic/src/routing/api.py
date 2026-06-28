# routing/api.py – REST API for cost‑aware routing
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from dataclasses import asdict
from .core import get_routing_balancer, Endpoint
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/routing", tags=["Cost‑Aware Routing"])

class AddEndpointRequest(BaseModel):
    id: str; url: str; provider: str; region: str; instance_type: str
    base_cost_per_hour: float = 0.05; latency_ms: float = 100; weight: float = 1.0; enabled: bool = True

class SetPolicyRequest(BaseModel):
    policy: str

@router.get("/route")
async def route_request(user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    decision = balancer.route_request()
    return asdict(decision)

@router.post("/policy")
async def set_policy(req: SetPolicyRequest, user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    success = balancer.set_policy(req.policy)
    if not success: raise HTTPException(400, "Invalid policy")
    return {"policy": req.policy, "status": "updated"}

@router.get("/policy")
async def get_policy(user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    return {"policy": balancer.current_policy.value}

@router.post("/endpoints")
async def add_endpoint(req: AddEndpointRequest, user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    ep = Endpoint(**req.dict())
    success = balancer.add_endpoint(ep)
    if not success: raise HTTPException(500, "Failed to add endpoint")
    return {"endpoint_id": ep.id, "status": "added"}

@router.get("/endpoints")
async def list_endpoints(user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    return {"endpoints": [asdict(ep) for ep in balancer.endpoints.values()]}

@router.put("/endpoints/{endpoint_id}/enable")
async def enable_endpoint(endpoint_id: str, enabled: bool = True, user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    success = balancer.enable_endpoint(endpoint_id, enabled)
    if not success: raise HTTPException(404, "Endpoint not found")
    return {"endpoint": endpoint_id, "enabled": enabled}

@router.get("/stats")
async def get_stats(user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    return balancer.get_stats()

@router.post("/optimize")
async def optimize_weights(user=Depends(require_permission("admin"))):
    balancer = get_routing_balancer()
    balancer.optimize_weights()
    return {"status": "weights_optimized"}
