# datamasking/api.py – REST API for data masking and tokenisation
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from .masking.mask_service import get_mask_service
from .tokenisation.token_service import get_token_service
from .pii.detector import get_pii_detector
from .policies.policy_loader import get_policy_loader
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/mask", tags=["Data Masking"])

class MaskTextRequest(BaseModel):
    text: str
    role: str = "user"
    preserve_tokens: bool = True

class MaskFieldRequest(BaseModel):
    value: str
    field_type: str
    mask_policy: str = "default"
    role: str = "user"

class TokenizeRequest(BaseModel):
    value: str
    data_type: str = "pii"
    ttl_seconds: Optional[int] = None

class DetokenizeRequest(BaseModel):
    token: str

@router.post("/text")
async def mask_text(req: MaskTextRequest, user: dict = Depends(require_permission("user"))):
    service = get_mask_service()
    masked = service.mask_text(req.text, req.role, req.preserve_tokens)
    return {"original_length": len(req.text), "masked": masked}

@router.post("/field")
async def mask_field(req: MaskFieldRequest, user: dict = Depends(require_permission("user"))):
    service = get_mask_service()
    masked = service.mask_field(req.value, req.field_type, req.mask_policy, req.role)
    return {"original_length": len(req.value), "masked": masked}

@router.post("/detect")
async def detect_pii(text: str, user: dict = Depends(require_permission("user"))):
    detector = get_pii_detector()
    detections = detector.detect(text)
    return {"detections": detections, "count": len(detections)}

@router.post("/tokenize")
async def tokenize(req: TokenizeRequest, user: dict = Depends(require_permission("user"))):
    service = get_token_service()
    token = service.tokenize(req.value, req.data_type, req.ttl_seconds)
    return {"token": token, "data_type": req.data_type, "ttl_seconds": req.ttl_seconds}

@router.post("/detokenize")
async def detokenize(req: DetokenizeRequest, user: dict = Depends(require_permission("user"))):
    service = get_token_service()
    original = service.detokenize(req.token)
    if original is None:
        raise HTTPException(404, "Token not found or expired")
    return {"original": original}

@router.get("/tokens")
async def list_tokens(limit: int = 100, user: dict = Depends(require_permission("admin"))):
    service = get_token_service()
    tokens = service.list_tokens(limit)
    return {"tokens": tokens}

@router.delete("/tokens/{token}")
async def delete_token(token: str, user: dict = Depends(require_permission("admin"))):
    service = get_token_service()
    if service.delete_token(token):
        return {"message": "Token deleted"}
    raise HTTPException(404, "Token not found")

@router.get("/policies")
async def get_policies(user: dict = Depends(require_permission("admin"))):
    loader = get_policy_loader()
    return {"policies": loader.policies}

@router.post("/policies/reload")
async def reload_policies(user: dict = Depends(require_permission("admin"))):
    loader = get_policy_loader()
    loader.reload()
    return {"message": "Policies reloaded"}

@router.post("/anonymize")
async def anonymize_text(text: str, user: dict = Depends(require_permission("user"))):
    detector = get_pii_detector()
    anonymized = detector.anonymise_text(text)
    return {"original": text, "anonymized": anonymized}
