# cost/api.py – REST API for cost optimization
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from .optimizer import get_optimizer, CostRecommendation
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/cost", tags=["Cost Optimization"])

class MetricIngest(BaseModel):
    resource_id: str
    resource_type: str
    provider: str
    region: str
    hourly_cost: float
    utilization_cpu: float
    utilization_memory: float
    utilization_disk: float

@router.post("/metrics")
async def ingest_metrics(metric: MetricIngest, user=Depends(require_permission("admin"))):
    from .optimizer import ResourceMetrics
    import time
    rm = ResourceMetrics(
        resource_id=metric.resource_id,
        resource_type=metric.resource_type,
        provider=metric.provider,
        region=metric.region,
        hourly_cost=metric.hourly_cost,
        utilization_cpu=metric.utilization_cpu,
        utilization_memory=metric.utilization_memory,
        utilization_disk=metric.utilization_disk,
        timestamp=int(time.time())
    )
    optimizer = get_optimizer()
    optimizer.ingest_metrics(rm)
    # also persist to disk
    import json, os
    os.makedirs("data/cost/metrics", exist_ok=True)
    with open(f"data/cost/metrics/{rm.resource_id}_{rm.timestamp}.json", 'w') as f:
        json.dump(rm.__dict__, f)
    return {"status": "ingested", "resource_id": metric.resource_id}

@router.get("/recommendations")
async def get_recommendations(limit: int = 50, user=Depends(require_permission("admin"))):
    optimizer = get_optimizer()
    recs = optimizer.get_recommendations(limit)
    return {"recommendations": recs, "count": len(recs)}

@router.get("/forecast")
async def get_forecast(days: int = 30, user=Depends(require_permission("admin"))):
    optimizer = get_optimizer()
    forecast = optimizer.forecast_cost(days)
    return forecast

@router.post("/optimize/run")
async def run_optimization_cycle(user=Depends(require_permission("admin"))):
    optimizer = get_optimizer()
    recs = optimizer.run_optimization_cycle()
    return {"cycle_completed": True, "recommendations_generated": len(recs)}
