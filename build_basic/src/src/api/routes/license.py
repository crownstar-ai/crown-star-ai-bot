# src/api/routes/license.py
"""
License management endpoints: activation, validation, status.
"""

import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

from src.core.logging_config import get_logger
from src.core.exceptions import LicenseInvalidError, ValidationError
from src.licensing.validator import LicenseValidator
from src.licensing.middleware import LicenseMiddleware

router = APIRouter()
logger = get_logger(__name__)

validator = LicenseValidator()


class ActivateLicenseRequest(BaseModel):
    license_key: str
    email: Optional[str] = None


@router.post("/activate")
async def activate_license(request: Request, req: ActivateLicenseRequest):
    """Activate a new license."""
    # Validate the license key
    valid, tier, details = validator.validate(req.license_key)
    if not valid:
        error = details.get("error", "Invalid license")
        if "expired" in error.lower():
            raise LicenseInvalidError("License has expired")
        else:
            raise LicenseInvalidError(error)
    
    # Store license in environment or database for persistence
    # In production, you'd save to DB
    os.environ["CROWNSTAR_LICENSE_KEY"] = req.license_key
    
    logger.info(f"License activated for tier {tier}", extra={"email": req.email, "tier": tier})
    return {
        "status": "activated",
        "tier": tier,
        "expires_at": details.get("expires_at"),
        "message": "License activated successfully"
    }


@router.get("/validate")
async def validate_license(request: Request):
    """Check if the current license is valid."""
    license_key = os.environ.get("CROWNSTAR_LICENSE_KEY")
    if not license_key:
        return {"status": "no_license", "tier": "free"}
    
    valid, tier, details = validator.validate(license_key)
    if not valid:
        return {"status": "invalid", "tier": None, "error": details.get("error")}
    
    return {
        "status": "valid",
        "tier": tier,
        "email": details.get("email"),
        "expires_at": details.get("expires_at"),
        "features": details.get("features", {}),
    }


@router.post("/deactivate")
async def deactivate_license(request: Request):
    """Deactivate the current license."""
    if "CROWNSTAR_LICENSE_KEY" in os.environ:
        del os.environ["CROWNSTAR_LICENSE_KEY"]
    logger.info("License deactivated")
    return {"status": "deactivated"}
