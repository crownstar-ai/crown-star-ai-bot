# graphql/api.py – REST API for GraphQL federation and gateway
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_graphql_manager, SubgraphDefinition
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/graphql", tags=["GraphQL Federation"])

class SubgraphRegisterRequest(BaseModel):
    name: str; url: str; schema_sdl: str; active: bool = True

class GraphQLQueryRequest(BaseModel):
    query: str; variables: Optional[Dict] = {}; operation_name: Optional[str] = None

@router.post("/subgraphs")
async def register_subgraph(req: SubgraphRegisterRequest, user=Depends(require_permission("admin"))):
    mgr = get_graphql_manager()
    sub = SubgraphDefinition(subgraph_id="", name=req.name, url=req.url, schema_sdl=req.schema_sdl, version=1, active=req.active, created_at=0, updated_at=0)
    sub_id = mgr.register_subgraph(sub)
    return {"subgraph_id": sub_id, "status": "registered"}

@router.get("/subgraphs")
async def list_subgraphs(user=Depends(require_permission("admin"))):
    mgr = get_graphql_manager()
    return {"subgraphs": mgr.get_subgraphs()}

@router.get("/supergraph")
async def get_supergraph_sdl(user=Depends(require_permission("admin"))):
    mgr = get_graphql_manager()
    return {"sdl": mgr.get_supergraph_sdl()}

@router.post("/query")
async def federated_query(req: GraphQLQueryRequest, request: Request, user=Depends(require_permission("admin"))):
    mgr = get_graphql_manager()
    headers = dict(request.headers)
    client_id = headers.get("X-Client-Id", "unknown")
    response = await mgr.federated_query(req.query, req.variables, headers, client_id)
    return response

@router.get("/gateway/status")
async def gateway_status(user=Depends(require_permission("admin"))):
    mgr = get_graphql_manager()
    return {"gateway_routes": list(mgr.gateway.routes.keys()), "subgraph_count": len(mgr.composer.subgraphs), "supergraph_built": mgr.planner.supergraph_schema is not None}
