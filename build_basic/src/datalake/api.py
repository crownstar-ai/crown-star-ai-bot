# datalake/api.py – REST API for data lake operations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import pandas as pd
from .lake_service import get_lake_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/datalake", tags=["Data Lake"])

class WriteEventsRequest(BaseModel):
    events: List[Dict]
    format: Optional[str] = None

class WriteConversationsRequest(BaseModel):
    conversations: List[Dict]
    format: Optional[str] = None

class WriteMetricsRequest(BaseModel):
    metrics: List[Dict]
    format: Optional[str] = None

class QueryRequest(BaseModel):
    table: str
    format: Optional[str] = None
    filter: Optional[str] = None
    version: Optional[int] = None
    limit: int = 100

@router.post("/write/events")
async def write_events(req: WriteEventsRequest, user: dict = Depends(require_permission("admin"))):
    lake = get_lake_service()
    success = lake.write_events(req.events, req.format)
    if success:
        return {"message": f"Written {len(req.events)} events"}
    raise HTTPException(500, "Write failed")

@router.post("/write/conversations")
async def write_conversations(req: WriteConversationsRequest, user: dict = Depends(require_permission("admin"))):
    lake = get_lake_service()
    success = lake.write_conversations(req.conversations, req.format)
    return {"message": f"Written {len(req.conversations)} conversations", "success": success}

@router.post("/write/metrics")
async def write_metrics(req: WriteMetricsRequest, user: dict = Depends(require_permission("admin"))):
    lake = get_lake_service()
    success = lake.write_metrics(req.metrics, req.format)
    return {"message": f"Written {len(req.metrics)} metrics", "success": success}

@router.post("/query")
async def query_lake(req: QueryRequest, user: dict = Depends(require_permission("user"))):
    lake = get_lake_service()
    df = lake.query(req.table, req.format, req.filter, req.version)
    if df.empty:
        return {"rows": []}
    # Convert to JSON (limit rows)
    records = df.head(req.limit).to_dict(orient="records")
    return {"rows": records, "count": len(records), "total": len(df)}

@router.get("/tables")
async def list_tables(user: dict = Depends(require_permission("user"))):
    lake = get_lake_service()
    # For Delta, list directories; for Iceberg, use catalog
    import os
    from pathlib import Path
    base = Path("data/lake/delta")
    tables = [p.name for p in base.iterdir() if p.is_dir()] if base.exists() else []
    return {"tables": tables, "format": lake.format}

@router.get("/versions/{table}")
async def get_versions(table: str, format: str = None, user: dict = Depends(require_permission("admin"))):
    lake = get_lake_service()
    versions = lake.get_versions(table, format)
    return {"versions": versions}

@router.post("/optimize/{table}")
async def optimize_table(table: str, format: str = None, user: dict = Depends(require_permission("admin"))):
    lake = get_lake_service()
    success = lake.optimize(table, format)
    return {"message": f"Optimization {'started' if success else 'failed'}"}

@router.post("/vacuum/{table}")
async def vacuum_table(table: str, retention_hours: int = 168, format: str = None, user: dict = Depends(require_permission("admin"))):
    lake = get_lake_service()
    success = lake.vacuum(table, retention_hours, format)
    return {"message": f"Vacuum {'completed' if success else 'failed'}", "retention_hours": retention_hours}
