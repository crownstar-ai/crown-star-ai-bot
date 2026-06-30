# src/api/routes/analytics.py
"""
Analytics API endpoints for usage and performance metrics.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from src.core.logging_config import get_logger
from src.core.exceptions import ForbiddenError, ValidationError
from src.analytics.usage_tracker import UsageTracker

router = APIRouter()
logger = get_logger(__name__)

usage_tracker = UsageTracker()


@router.get("/usage/daily")
async def get_daily_usage(request: Request, user_id: Optional[str] = None):
    """Get daily usage for the current user or admin for a specific user."""
    current_tier = getattr(request.state, "tier", "free")
    if current_tier not in ["pro", "enterprise"]:
        raise ForbiddenError("Analytics requires Pro or Enterprise tier")
    
    if not user_id:
        user_id = request.state.get("user_id")  # from auth
    if not user_id:
        raise ValidationError("user_id required")
    
    today = datetime.utcnow().date().isoformat()
    count = usage_tracker.get_daily_count(user_id)
    return {"user_id": user_id, "date": today, "requests": count}


@router.get("/usage/summary")
async def get_usage_summary(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Get aggregated usage summary."""
    current_tier = getattr(request.state, "tier", "free")
    if current_tier not in ["pro", "enterprise"]:
        raise ForbiddenError("Analytics requires Pro or Enterprise tier")
    
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = datetime.utcnow().date().isoformat()
    
    if not user_id:
        user_id = request.state.get("user_id")
    if not user_id:
        raise ValidationError("user_id required")
    
    summary = usage_tracker.get_usage_summary(user_id, start_date, end_date)
    return {"user_id": user_id, "start_date": start_date, "end_date": end_date, "summary": summary}


@router.get("/tenant/usage")
async def get_tenant_usage(request: Request, start_date: str, end_date: str):
    """Get usage for all users in the current tenant (Enterprise only)."""
    current_tier = getattr(request.state, "tier", "free")
    if current_tier != "enterprise":
        raise ForbiddenError("Tenant analytics requires Enterprise tier")
    
    tenant_id = request.state.get("tenant_id")
    if not tenant_id:
        raise ValidationError("tenant_id not available")
    
    results = usage_tracker.get_tenant_usage(tenant_id, start_date, end_date)
    return {"tenant_id": tenant_id, "start_date": start_date, "end_date": end_date, "usage": results}
