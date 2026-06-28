# logging/log_query_api.py – Proxy to Loki for log queries
from fastapi import APIRouter, HTTPException, Depends, Request
import httpx
import os
from typing import Optional
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/logs", tags=["Logs"])

LOKI_URL = os.environ.get("LOKI_URL", "http://localhost:3100")

@router.get("/query")
async def query_logs(
    query: str,
    limit: int = 100,
    start: Optional[int] = None,
    end: Optional[int] = None,
    direction: str = "backward",
    user: dict = Depends(require_permission("audit:view"))
):
    """Query logs using LogQL"""
    params = {
        "query": query,
        "limit": limit,
        "direction": direction
    }
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
        if resp.status_code != 200:
            raise HTTPException(502, "Loki query failed")
        return resp.json()

@router.get("/labels")
async def get_labels(user: dict = Depends(require_permission("audit:view"))):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{LOKI_URL}/loki/api/v1/labels")
        return resp.json()

@router.get("/label/{name}/values")
async def get_label_values(name: str, user: dict = Depends(require_permission("audit:view"))):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{LOKI_URL}/loki/api/v1/label/{name}/values")
        return resp.json()
