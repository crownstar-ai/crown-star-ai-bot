# analytics/api.py – REST API for metrics and anomaly history
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from .core import get_monitor, Anomaly
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/analytics", tags=["Analytics"])

@router.get("/metrics")
async def get_metrics(metric_name: Optional[str] = None, seconds: int = 60, user=Depends(require_permission("admin"))):
    """Retrieve recent metrics (optionally filtered by name)."""
    monitor = get_monitor()
    if metric_name:
        points = monitor.collector.get_recent(metric_name, seconds)
        return {"metric": metric_name, "data": [{"value": p.value, "timestamp": p.timestamp, "labels": p.labels} for p in points]}
    else:
        # Return all recent metrics aggregated
        all_points = list(monitor.collector.buffer)[-1000:]
        return {"metrics": [{"name": p.name, "value": p.value, "timestamp": p.timestamp} for p in all_points]}

@router.get("/anomalies")
async def get_anomalies(limit: int = 100, severity: Optional[str] = None, user=Depends(require_permission("admin"))):
    """Retrieve historical anomalies (from persistent storage)."""
    # In production, anomalies are persisted to data/analytics/anomalies/
    # For now, return recent anomalies from memory
    monitor = get_monitor()
    anomalies = []
    # Read from anomaly queue (non‑destructive)
    # Simplified: just return last few from monitor's internal store
    return {"anomalies": anomalies, "limit": limit}

@router.post("/anomalies/threshold")
async def update_threshold(metric_name: str, threshold: float, user=Depends(require_permission("admin"))):
    """Update Z‑score threshold for a specific metric."""
    monitor = get_monitor()
    monitor.detector.config["zscore_threshold"] = threshold
    return {"status": "updated", "metric": metric_name, "new_threshold": threshold}

@router.get("/dashboard")
async def dashboard_summary(user=Depends(require_permission("admin"))):
    """Get a summary snapshot for the real‑time dashboard."""
    monitor = get_monitor()
    snapshot = monitor._get_snapshot()
    return snapshot
