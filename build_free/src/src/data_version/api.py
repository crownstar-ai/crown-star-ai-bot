# data_version/api.py – REST API for data versioning and lineage
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from dataclasses import asdict
from .core import get_data_version_manager, DataVersion
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/data/version", tags=["Data Versioning"])

class CommitRequest(BaseModel):
    dataset_path: str
    message: str
    author: str = "system"
    run_quality: bool = True

class TagRequest(BaseModel):
    version_id: str
    tag: str

class CheckoutRequest(BaseModel):
    version_id: str
    target_path: str

class DiffRequest(BaseModel):
    version_a: str
    version_b: str

class LinkRequest(BaseModel):
    dataset_version_id: str
    model_version_id: str
    relation: str = "trained_on"
    metadata: Optional[Dict] = None

@router.post("/commit")
async def commit_dataset(req: CommitRequest, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    version = mgr.commit_dataset(req.dataset_path, req.message, req.author, req.run_quality)
    return asdict(version)

@router.post("/tag")
async def tag_version(req: TagRequest, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    success = mgr.tag_version(req.version_id, req.tag)
    if not success:
        raise HTTPException(404, "Version not found")
    return {"status": "tagged", "version": req.version_id, "tag": req.tag}

@router.post("/checkout")
async def checkout_version(req: CheckoutRequest, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    success = mgr.checkout(req.version_id, req.target_path)
    if not success:
        raise HTTPException(404, "Version not found")
    return {"status": "checked_out", "version": req.version_id, "target": req.target_path}

@router.post("/diff")
async def diff_versions(req: DiffRequest, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    diff = mgr.diff(req.version_a, req.version_b)
    return diff

@router.get("/versions/{dataset_name}")
async def list_versions(dataset_name: str, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    versions = mgr.list_versions(dataset_name)
    return {"versions": [asdict(v) for v in versions]}

@router.post("/lineage/link")
async def link_dataset_to_model(req: LinkRequest, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    edge_id = mgr.link_dataset_to_model(req.dataset_version_id, req.model_version_id, req.relation, req.metadata)
    return {"edge_id": edge_id}

@router.get("/lineage/model/{model_version_id}")
async def get_model_lineage(model_version_id: str, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    lineage = mgr.get_model_lineage(model_version_id)
    return lineage

@router.get("/lineage/{node_type}/{node_id}")
async def get_lineage_graph(node_type: str, node_id: str, user=Depends(require_permission("admin"))):
    mgr = get_data_version_manager()
    edges = mgr.get_lineage_graph(node_id, node_type)
    return {"edges": [asdict(e) for e in edges]}
