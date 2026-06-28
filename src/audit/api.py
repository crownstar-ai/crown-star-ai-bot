# audit/api.py – REST API for audit trails and compliance
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json
from .audit_service import get_audit_service, AuditEvent
from .compliance.report_generators import get_compliance
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/audit", tags=["Audit"])

class LogEventRequest(BaseModel):
    event_type: str
    resource: str
    action: str
    details: dict = {}

@router.post("/log")
async def log_event(req: LogEventRequest, request: Request, user: dict = Depends(require_permission("user"))):
    audit = get_audit_service()
    tenant_id = request.state.tenant_id if hasattr(request.state, "tenant_id") else "default"
    event = AuditEvent(
        event_type=req.event_type,
        user_id=user.get("user_id", "system"),
        tenant_id=tenant_id,
        resource=req.resource,
        action=req.action,
        details=req.details,
        source_ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    audit.log(event)
    return {"message": "Event logged", "event_id": event.event_id}

@router.get("/search")
async def search_audit(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    event_type: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(require_permission("auditor"))
):
    audit = get_audit_service()
    start_dt = datetime.fromisoformat(start) if start else datetime(2000,1,1)
    end_dt = datetime.fromisoformat(end) if end else datetime.utcnow()
    results = audit.search_events(start_dt, end_dt, user_id, tenant_id, event_type, resource, action, limit)
    return {"events": results, "count": len(results)}

@router.get("/verify")
async def verify_audit_integrity(event_id: Optional[str] = None, user: dict = Depends(require_permission("auditor"))):
    audit = get_audit_service()
    result = audit.verify_integrity(event_id)
    return result

@router.post("/retention/apply")
async def apply_retention(user: dict = Depends(require_permission("admin"))):
    audit = get_audit_service()
    result = audit.apply_retention()
    return result

@router.get("/export/csv")
async def export_audit_csv(start: str, end: str, user: dict = Depends(require_permission("auditor"))):
    audit = get_audit_service()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        count = audit.export_to_csv(start_dt, end_dt, tmp.name)
        with open(tmp.name, "rb") as f:
            content = f.read()
    return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=audit_{start}_{end}.csv"})

@router.get("/report/gdpr/sar")
async def gdpr_subject_access(user_id: str, start: str, end: str, user: dict = Depends(require_permission("compliance"))):
    comp = get_compliance()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    report = comp.gdpr_data_subject_access(user_id, start_dt, end_dt)
    return report

@router.get("/report/gdpr/erasure")
async def gdpr_erasure(user_id: str, deletion_date: str, user: dict = Depends(require_permission("compliance"))):
    comp = get_compliance()
    del_dt = datetime.fromisoformat(deletion_date)
    report = comp.gdpr_deletion_manifest(user_id, del_dt)
    return report

@router.get("/report/soc2/{control_id}")
async def soc2_report(control_id: str, start: str, end: str, user: dict = Depends(require_permission("compliance"))):
    comp = get_compliance()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    report = comp.soc2_control_evidence(control_id, start_dt, end_dt)
    return report

@router.get("/report/hipaa/access")
async def hipaa_access(user_id: str, start: str, end: str, user: dict = Depends(require_permission("compliance"))):
    comp = get_compliance()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    report = comp.hipaa_access_report(user_id, start_dt, end_dt)
    return report

@router.get("/report/pci")
async def pci_report(start: str, end: str, user: dict = Depends(require_permission("compliance"))):
    comp = get_compliance()
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    report = comp.generate_pci_dss_report(start_dt, end_dt)
    return report
