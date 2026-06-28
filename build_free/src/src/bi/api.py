# bi/api.py – REST API for BI data extraction
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .service import get_bi_service
from security.dependencies import require_permission
import tempfile

router = APIRouter(prefix="/v1/bi", tags=["Business Intelligence"])

class ExportRequest(BaseModel):
    start_date: str
    end_date: str
    format: str = "csv"  # csv, json, parquet, excel

@router.post("/export")
async def export_data(req: ExportRequest, user: dict = Depends(require_permission("analytics:view"))):
    service = get_bi_service()
    with tempfile.NamedTemporaryFile(suffix=f".{req.format}", delete=False) as tmp:
        if req.format == "csv":
            service.export_csv(req.start_date, req.end_date, tmp.name)
            media_type = "text/csv"
        elif req.format == "json":
            service.export_json(req.start_date, req.end_date, tmp.name)
            media_type = "application/json"
        elif req.format == "parquet":
            service.export_parquet(req.start_date, req.end_date, tmp.name)
            media_type = "application/parquet"
        elif req.format == "excel":
            service.export_excel(req.start_date, req.end_date, tmp.name)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise HTTPException(400, "Unsupported format")
        
        with open(tmp.name, "rb") as f:
            content = f.read()
        return Response(content=content, media_type=media_type, headers={
            "Content-Disposition": f"attachment; filename=crownstar_report_{req.start_date}_{req.end_date}.{req.format}"
        })

@router.get("/usage")
async def usage_summary(start_date: str, end_date: str, user: dict = Depends(require_permission("analytics:view"))):
    service = get_bi_service()
    df = service.get_usage_report(start_date, end_date)
    return df.to_dict(orient="records")

@router.get("/by-tier")
async def by_tier(start_date: str, end_date: str, user: dict = Depends(require_permission("analytics:view"))):
    service = get_bi_service()
    df = service.get_by_tier(start_date, end_date)
    return df.to_dict(orient="records")

@router.get("/by-model")
async def by_model(start_date: str, end_date: str, user: dict = Depends(require_permission("analytics:view"))):
    service = get_bi_service()
    df = service.get_by_model(start_date, end_date)
    return df.to_dict(orient="records")
