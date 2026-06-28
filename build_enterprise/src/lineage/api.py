# lineage/api.py – REST endpoints for lineage and governance
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
from .service import get_lineage
from governance.service import get_governance
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/lineage", tags=["Data Lineage"])

class LineageEventRequest(BaseModel):
    event_type: str  # START, COMPLETE, FAIL
    job_name: str
    inputs: List[Dict] = []
    outputs: List[Dict] = []
    facets: Dict = {}

@router.post("/events")
async def emit_lineage_event(req: LineageEventRequest, user: dict = Depends(require_permission("admin"))):
    svc = get_lineage()
    svc.emitter.emit(req.event_type, {
        "job_name": req.job_name,
        "inputs": req.inputs,
        "outputs": req.outputs,
        "facets": req.facets
    })
    return {"status": "emitted"}

@router.get("/graph/dataset/{dataset_name}")
async def get_dataset_lineage(dataset_name: str, user: dict = Depends(require_permission("user"))):
    svc = get_lineage()
    graph = svc.get_lineage_graph(dataset_name=dataset_name)
    return graph

@router.get("/graph/job/{job_name}")
async def get_job_lineage(job_name: str, user: dict = Depends(require_permission("user"))):
    svc = get_lineage()
    graph = svc.get_lineage_graph(job_name=job_name)
    return graph

@router.get("/search")
async def search_lineage(q: str, user: dict = Depends(require_permission("user"))):
    svc = get_lineage()
    results = svc.marquez.search_lineage(q)
    return results

@router.get("/governance/policies")
async def get_governance_policies(user: dict = Depends(require_permission("admin"))):
    gov = get_governance()
    return gov.get_policy_summary()

@router.post("/governance/retention/apply")
async def apply_retention(user: dict = Depends(require_permission("admin"))):
    gov = get_governance()
    deleted = gov.apply_retention_policy()
    return {"deleted_files": deleted, "count": len(deleted)}

@router.post("/governance/anonymize")
async def anonymize_text(text: str, user: dict = Depends(require_permission("user"))):
    gov = get_governance()
    anonymized = gov.anonymize(text)
    return {"original_length": len(text), "anonymized": anonymized}
