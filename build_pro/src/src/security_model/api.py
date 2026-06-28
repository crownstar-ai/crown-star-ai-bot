# security_model/api.py – REST API for model security
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List
from .core import get_sec_manager, AttackResult, Watermark
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/security", tags=["Model Security"])

class AttackRequest(BaseModel):
    model_path: str
    data_path: str
    attack: str = "fgsm"

class WatermarkRequest(BaseModel):
    model_path: str
    secret: str

class WatermarkVerifyRequest(BaseModel):
    model_path: str
    watermark: Dict
    secret: str

class EncryptRequest(BaseModel):
    model_path: str
    output_path: str

class DecryptRequest(BaseModel):
    encrypted_path: str
    output_path: str

@router.post("/adversarial/evaluate")
async def evaluate_robustness(req: AttackRequest, user=Depends(require_permission("admin"))):
    mgr = get_sec_manager()
    # Load model and data (simplified)
    return {"attack": req.attack, "status": "evaluation_started"}

@router.post("/watermark/embed")
async def embed_watermark(req: WatermarkRequest, user=Depends(require_permission("admin"))):
    mgr = get_sec_manager()
    # Load model, embed
    watermark = mgr.embed_watermark(None, req.secret)  # placeholder
    return {"watermark": asdict(watermark)}

@router.post("/watermark/verify")
async def verify_watermark(req: WatermarkVerifyRequest, user=Depends(require_permission("admin"))):
    mgr = get_sec_manager()
    wm = Watermark(**req.watermark)
    valid = mgr.verify_watermark(None, wm, req.secret)
    return {"valid": valid}

@router.post("/encrypt")
async def encrypt_model(req: EncryptRequest, user=Depends(require_permission("admin"))):
    mgr = get_sec_manager()
    mgr.encrypt_model({}, req.output_path)
    return {"encrypted_path": req.output_path}

@router.post("/decrypt")
async def decrypt_model(req: DecryptRequest, user=Depends(require_permission("admin"))):
    mgr = get_sec_manager()
    state = mgr.decrypt_model(req.encrypted_path)
    return {"status": "decrypted", "keys": list(state.keys()) if state else []}

@router.get("/robust/aggregate")
async def robust_aggregate(user=Depends(require_permission("admin"))):
    mgr = get_sec_manager()
    # Placeholder
    return {"aggregator": mgr.config["poison"]["aggregator"]}
