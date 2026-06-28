# knowledge/api.py – REST API for knowledge graph and GNN
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from .core import get_kg_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/knowledge", tags=["Knowledge Graph"])

class EntityAddRequest(BaseModel):
    entity_id: str
    label: str
    properties: Optional[Dict] = None

class RelationAddRequest(BaseModel):
    source: str
    target: str
    predicate: str
    weight: float = 1.0
    properties: Optional[Dict] = None

class QueryRequest(BaseModel):
    cypher: str

class TrainGNNRequest(BaseModel):
    epochs: Optional[int] = None

@router.post("/entities")
async def add_entity(req: EntityAddRequest, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    entity_id = mgr.add_entity(req.entity_id, req.label, req.properties)
    return {"entity_id": entity_id, "status": "created"}

@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    entity = mgr.graph.entities.get(entity_id)
    if not entity:
        raise HTTPException(404, "Entity not found")
    from dataclasses import asdict
    return {"entity": asdict(entity)}

@router.post("/relations")
async def add_relation(req: RelationAddRequest, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    rel_id = mgr.add_relation(req.source, req.target, req.predicate, req.weight, req.properties)
    return {"relation_id": rel_id, "status": "created"}

@router.post("/query")
async def query_graph(req: QueryRequest, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    results = mgr.query(req.cypher)
    return {"results": results}

@router.post("/gnn/train")
async def train_gnn(req: TrainGNNRequest, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    result = mgr.train_gnn(req.epochs)
    return result

@router.post("/infer/{source}/{target}")
async def infer_relation(source: str, target: str, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    predictions = mgr.infer_relations(source, target)
    return {"source": source, "target": target, "predictions": [{"predicate": p, "score": s} for p, s in predictions]}

@router.get("/embedding/{entity_id}")
async def get_embedding(entity_id: str, user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    emb = mgr.get_entity_embedding(entity_id)
    if emb is None:
        raise HTTPException(404, "Entity embedding not found (train GNN first)")
    return {"entity_id": entity_id, "embedding": emb, "dimension": len(emb)}

@router.get("/stats")
async def graph_stats(user=Depends(require_permission("admin"))):
    mgr = get_kg_manager()
    return mgr.get_graph_stats()
