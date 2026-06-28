# gateway/api.py – REST API for gateway management
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import subprocess
import json
from ..federation.gateway import _federated_gateway
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/gateway", tags=["API Gateway"])

@router.get("/graphql/schema")
async def get_federated_schema(user: dict = Depends(require_permission("admin"))):
    from ..federation.gateway import composed_schema
    return {"schema": str(composed_schema)}

@router.get("/subgraphs")
async def list_subgraphs(user: dict = Depends(require_permission("admin"))):
    subgraphs = _federated_gateway.subgraphs
    return {"subgraphs": subgraphs}

@router.post("/subgraphs/{name}/reload")
async def reload_subgraph(name: str, user: dict = Depends(require_permission("admin"))):
    # Trigger subgraph schema refresh
    return {"message": f"Subgraph {name} reload requested"}

@router.get("/ws/status")
async def ws_gateway_status(user: dict = Depends(require_permission("admin"))):
    from ..websocket.gateway import _ws_gateway
    if _ws_gateway:
        return {"status": "running", "connections": len(_ws_gateway.connections), "backends": list(_ws_gateway.backend_connections.keys())}
    return {"status": "not running"}

@router.get("/federation/health")
async def federation_health():
    # Check Apollo Router health
    import requests
    try:
        resp = requests.get("http://localhost:4000/health", timeout=2)
        return {"apollo_router": "healthy" if resp.status_code == 200 else "unhealthy"}
    except:
        return {"apollo_router": "unreachable"}
