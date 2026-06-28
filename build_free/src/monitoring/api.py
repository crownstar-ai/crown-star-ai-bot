# monitoring/api.py – REST API for drift detection and performance monitoring
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import numpy as np
import time
from dataclasses import asdict
from .core import get_monitor, PerformanceSnapshot, DriftReport, DriftType, AlertSeverity
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/monitor", tags=["Model Monitoring"])

class SetReferenceRequest(BaseModel):
    model_id: str
    version_id: str
    reference_data: List[List[float]]
    feature_names: List[str]

class DataDriftRequest(BaseModel):
    model_id: str
    version_id: str
    current_data: List[List[float]]
    feature_names: List[str]

class ConceptDriftRequest(BaseModel):
    model_id: str
    version_id: str
    predictions: List[float]
    ground_truth: List[float]

class PerformanceSnapshotRequest(BaseModel):
    model_id: str
    version_id: str
    accuracy: Optional[float] = None
    latency_ms: float
    throughput_rps: float
    error_rate: float
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0

@router.post("/reference")
async def set_reference(req: SetReferenceRequest, user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    ref_np = np.array(req.reference_data)
    mgr.set_reference(req.model_id, req.version_id, ref_np, req.feature_names)
    return {"status": "reference_stored"}

@router.post("/drift/data")
async def check_data_drift(req: DataDriftRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    cur_np = np.array(req.current_data)
    reports = mgr.check_data_drift(req.model_id, req.version_id, cur_np, req.feature_names)
    for r in reports:
        mgr._send_alert(r)
    return {"reports": [asdict(r) for r in reports]}

@router.post("/drift/concept")
async def check_concept_drift(req: ConceptDriftRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    reports = mgr.check_concept_drift(req.model_id, req.version_id, req.predictions, req.ground_truth)
    for r in reports:
        mgr._send_alert(r)
    return {"reports": [asdict(r) for r in reports]}

@router.post("/performance")
async def record_performance(req: PerformanceSnapshotRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    snapshot = PerformanceSnapshot(
        model_id=req.model_id,
        version_id=req.version_id,
        timestamp=int(time.time()),
        accuracy=req.accuracy,
        latency_ms=req.latency_ms,
        throughput_rps=req.throughput_rps,
        error_rate=req.error_rate,
        cpu_usage=req.cpu_usage,
        memory_usage_mb=req.memory_usage_mb
    )
    reports = mgr.record_performance(snapshot)
    for r in reports:
        mgr._send_alert(r)
    return {"snapshot": asdict(snapshot), "anomalies": [asdict(r) for r in reports]}

@router.get("/alerts")
async def get_alerts(model_id: Optional[str] = None, severity: Optional[str] = None, limit: int = 100, user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    alerts = mgr.get_alerts(model_id, severity, limit)
    return {"alerts": [asdict(a) for a in alerts]}

@router.get("/config")
async def get_config(user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    return mgr.config

@router.post("/config")
async def update_config(config: Dict, user=Depends(require_permission("admin"))):
    mgr = get_monitor()
    mgr.config.update(config)
    import json
    with open("config/monitoring/config.json", 'w') as f:
        json.dump(mgr.config, f, indent=2)
    return {"status": "config_updated"}
