# security/oidc/api.py – OIDC metadata and token endpoints
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import json
import os
from ..oidc.oidc_service import get_oidc_service
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/security", tags=["Security Advanced"])

@router.get("/.well-known/openid-configuration")
async def oidc_discovery(request: Request):
    """OIDC Discovery endpoint for CrownStar as an OIDC provider (stub)"""
    base_url = str(request.base_url).rstrip("/")
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/v1/security/oauth2/authorize",
        "token_endpoint": f"{base_url}/v1/security/oauth2/token",
        "userinfo_endpoint": f"{base_url}/v1/security/oidc/userinfo",
        "jwks_uri": f"{base_url}/v1/security/oauth2/jwks",
        "response_types_supported": ["code", "token", "id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email", "offline_access"]
    }

@router.post("/oidc/token/introspect")
async def introspect_token(token: str, provider: Optional[str] = None, user: dict = Depends(require_permission("admin"))):
    """Introspect token from external OIDC provider"""
    svc = get_oidc_service()
    payload = svc.verify_token(token, provider)
    if not payload:
        raise HTTPException(404, "Token invalid")
    return {"active": True, "payload": payload}

@router.get("/oidc/userinfo")
async def oidc_userinfo(request: Request, user: dict = Depends(require_permission("user"))):
    """Return userinfo for current token (OIDC standard)"""
    # This would extract from request.state.oidc_user
    oidc_user = getattr(request.state, "oidc_user", {})
    return {
        "sub": oidc_user.get("sub"),
        "email": oidc_user.get("email"),
        "name": oidc_user.get("name"),
        "preferred_username": oidc_user.get("preferred_username")
    }

@router.get("/mtls/status")
async def mtls_status(user: dict = Depends(require_permission("admin"))):
    from ..mtls.mtls_service import get_mtls_validator
    validator = get_mtls_validator()
    return {
        "mtls_enabled": validator.require_client_cert,
        "ca_loaded": validator._ca_cert is not None
    }

@router.post("/mtls/test")
async def test_mtls(request: Request, user: dict = Depends(require_permission("admin"))):
    cert_subject = getattr(request.state, "client_cert_subject", None)
    return {"mtls_verified": cert_subject is not None, "subject": cert_subject}
