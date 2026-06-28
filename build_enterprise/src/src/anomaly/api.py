# anomaly/api.py – REST API for anomaly detection and self‑healing
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from .detector import get_anomaly_detector
from .remediation.orchestrator import get_healing_orchestrator
from .monitoring_daemon import get_monitoring_daemon
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/anomaly", tags=["Anomaly"])

@router.get("/status")
async def anomaly_status(user: dict = Depends(require_permission("admin"))):
    detector = get_anomaly_detector()
    stats = {
        "metrics_buffers": {k: len(v) for k, v in detector.metrics_buffer.items()},
        "anomaly_history_count": len(detector.anomaly_history),
        "config": detector.config
    }
    return stats

@router.get("/history")
async def anomaly_history(limit: int = 50, user: dict = Depends(require_permission("admin"))):
    detector = get_anomaly_detector()
    return {"anomalies": detector.anomaly_history[-limit:]}

@router.post("/detect")
async def detect_anomaly(metric_name: str, value: float, user: dict = Depends(require_permission("admin"))):
    detector = get_anomaly_detector()
    detector.add_metric(metric_name, value)
    result = detector.detect(metric_name, value)
    return result

@router.get("/remediation/history")
async def remediation_history(limit: int = 50, user: dict = Depends(require_permission("admin"))):
    healer = get_healing_orchestrator()
    return {"actions": healer.get_history(limit)}

@router.post("/remediation/trigger")
async def trigger_remediation(anomaly: Dict, user: dict = Depends(require_permission("admin"))):
    healer = get_healing_orchestrator()
    success = healer.handle_anomaly(anomaly)
    return {"success": success}

@router.post("/daemon/start")
async def start_daemon(user: dict = Depends(require_permission("admin"))):
    daemon = get_monitoring_daemon()
    daemon.start()
    return {"status": "started"}

@router.post("/daemon/stop")
async def stop_daemon(user: dict = Depends(require_permission("admin"))):
    daemon = get_monitoring_daemon()
    daemon.stop()
    return {"status": "stopped"}
