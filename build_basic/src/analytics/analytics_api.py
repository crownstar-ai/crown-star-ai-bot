# analytics/analytics_api.py – FastAPI endpoints for analytics and billing
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from .analytics_service import AnalyticsService
from .billing_engine import BillingEngine
from .report_generator import ReportGenerator
from fastapi.responses import JSONResponse, Response

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])

# Global instances (set in main)
analytics_service = None
report_generator = None

def get_analytics():
    if analytics_service is None:
        raise HTTPException(503, "Analytics service not initialized")
    return analytics_service

def get_reports():
    if report_generator is None:
        raise HTTPException(503, "Report generator not initialized")
    return report_generator

@router.get("/usage/summary")
async def usage_summary(
    start_date: str = None,
    end_date: str = None,
    analytics = Depends(get_analytics)
):
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()
    summary = analytics.get_usage_summary(start_date, end_date)
    return summary

@router.get("/usage/by-tier")
async def usage_by_tier(
    start_date: str = None,
    end_date: str = None,
    analytics = Depends(get_analytics)
):
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()
    return analytics.get_usage_by_tier(start_date, end_date)

@router.get("/usage/by-model")
async def usage_by_model(
    start_date: str = None,
    end_date: str = None,
    analytics = Depends(get_analytics)
):
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()
    return analytics.get_usage_by_model(start_date, end_date)

@router.get("/usage/modules")
async def usage_modules(
    start_date: str = None,
    end_date: str = None,
    analytics = Depends(get_analytics)
):
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()
    return analytics.get_module_usage(start_date, end_date)

class ReportRequest(BaseModel):
    start_date: str
    end_date: str
    format: str = "csv"  # csv, json, html, pdf

@router.post("/report")
async def generate_report(
    req: ReportRequest,
    analytics = Depends(get_analytics),
    reports = Depends(get_reports)
):
    if req.format == "csv":
        content = reports.generate_csv(req.start_date, req.end_date)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=report_{req.start_date}_{req.end_date}.csv"})
    elif req.format == "json":
        content = reports.generate_json(req.start_date, req.end_date)
        return Response(content=content, media_type="application/json")
    elif req.format == "html":
        content = reports.generate_html_summary(req.start_date, req.end_date)
        return Response(content=content, media_type="text/html")
    elif req.format == "pdf":
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            reports.generate_pdf(req.start_date, req.end_date, tmp.name)
            with open(tmp.name, "rb") as f:
                pdf_content = f.read()
            os.unlink(tmp.name)
        return Response(content=pdf_content, media_type="application/pdf")
    else:
        raise HTTPException(400, "Unsupported format")

@router.get("/billing/current")
async def current_billing(analytics = Depends(get_analytics)):
    # Simplified billing for pay-per-use user (would need user_id from auth)
    cost_info = BillingEngine.calculate_monthly_usage_cost("anonymous", analytics)
    return cost_info

@router.get("/pricing")
async def get_pricing():
    return {
        "tiers": BillingEngine.TIER_PRICES,
        "overage_rates": BillingEngine.OVERAGE_RATES,
        "limits": BillingEngine.TIER_LIMITS
    }
