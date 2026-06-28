# data_mesh/api.py – REST API for federated queries
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from .core import get_data_mesh_engine, DataSource, DataSourceType, QueryResult
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/data", tags=["Data Mesh"])

class SQLQueryRequest(BaseModel):
    sql: str
    use_cache: bool = True
    limit: int = 1000

class SourceAddRequest(BaseModel):
    name: str
    type: str
    connection_params: Dict
    domain: str = "default"
    tags: List[str] = []
    priority: int = 0

@router.post("/query")
async def execute_query(req: SQLQueryRequest, user=Depends(require_permission("admin"))):
    """Execute a federated SQL query across multiple data sources."""
    engine = get_data_mesh_engine()
    try:
        result = engine.execute(req.sql, req.use_cache, req.limit)
        return {
            "query_id": result.query_id,
            "columns": result.columns,
            "rows": result.rows[:100],  # limit response size
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "cached": result.cached
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@router.get("/sources")
async def list_sources(user=Depends(require_permission("admin"))):
    """List all registered data sources."""
    engine = get_data_mesh_engine()
    return {"sources": engine.get_sources()}

@router.post("/sources")
async def add_source(req: SourceAddRequest, user=Depends(require_permission("admin"))):
    """Register a new data source."""
    engine = get_data_mesh_engine()
    src = DataSource(
        name=req.name,
        type=DataSourceType(req.type),
        connection_params=req.connection_params,
        domain=req.domain,
        tags=req.tags,
        priority=req.priority
    )
    engine.add_source(src)
    return {"status": "added", "source": req.name}

@router.get("/schema/{source_name}")
async def get_schema(source_name: str, user=Depends(require_permission("admin"))):
    """Get schema (tables/columns) for a data source."""
    engine = get_data_mesh_engine()
    schema = engine.get_schema(source_name)
    return schema

@router.post("/cache/clear")
async def clear_query_cache(user=Depends(require_permission("admin"))):
    """Clear the federated query cache."""
    engine = get_data_mesh_engine()
    engine.query_cache.clear()
    return {"status": "cache cleared"}
