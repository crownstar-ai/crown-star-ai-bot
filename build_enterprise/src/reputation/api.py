# reputation/api.py – REST API for reputation and trust scoring
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import hashlib, time
from dataclasses import asdict
from .core import get_rep_manager, Attestation, AttestationType, TrustEntityType
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/reputation", tags=["Reputation & Trust"])

class AttestationRequest(BaseModel):
    entity_id: str; entity_type: str; attestation_type: str; issuer_did: str
    rating: float; comment: Optional[str] = None; expiry: Optional[int] = None; metadata: Optional[Dict] = None

class SoulboundMintRequest(BaseModel):
    entity_id: str; chain: str = "ethereum"; metadata_uri: str = ""

@router.get("/score/{entity_id}")
async def get_reputation_score(entity_id: str, user=Depends(require_permission("admin"))):
    mgr = get_rep_manager(); score = mgr.get_score(entity_id)
    if not score: raise HTTPException(404, "No reputation data found")
    return asdict(score)

@router.post("/attest")
async def add_attestation(req: AttestationRequest, user=Depends(require_permission("admin"))):
    mgr = get_rep_manager()
    att = Attestation(attestation_id=hashlib.md5(f"{req.entity_id}_{req.issuer_did}_{time.time()}".encode()).hexdigest()[:16], entity_id=req.entity_id, entity_type=TrustEntityType(req.entity_type), attestation_type=AttestationType(req.attestation_type), issuer_did=req.issuer_did, rating=req.rating, comment=req.comment, timestamp=int(time.time()), expiry=req.expiry, metadata=req.metadata or {})
    mgr.add_attestation(att)
    return {"attestation_id": att.attestation_id, "status": "recorded"}

@router.get("/attestations/{entity_id}")
async def get_attestations(entity_id: str, user=Depends(require_permission("admin"))):
    mgr = get_rep_manager(); atts = mgr.store.get_attestations(entity_id)
    return {"attestations": [asdict(a) for a in atts]}

@router.post("/soulbound/mint")
async def mint_soulbound(req: SoulboundMintRequest, user=Depends(require_permission("admin"))):
    mgr = get_rep_manager(); token = mgr.mint_soulbound_token(req.entity_id, req.chain, req.metadata_uri)
    if not token: raise HTTPException(503, "Soulbound token service unavailable")
    return asdict(token)

@router.post("/soulbound/revoke/{token_id}")
async def revoke_soulbound(token_id: str, user=Depends(require_permission("admin"))):
    mgr = get_rep_manager(); success = mgr.revoke_soulbound_token(token_id)
    if not success: raise HTTPException(404, "Token not found or revocation failed")
    return {"status": "revoked"}

@router.post("/oracle/aggregate")
async def aggregate_reputation(entity_id: str, user=Depends(require_permission("admin"))):
    mgr = get_rep_manager(); score = mgr.aggregate_reputation(entity_id)
    return asdict(score)
