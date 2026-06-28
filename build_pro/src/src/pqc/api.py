# pqc/api.py – REST API for post‑quantum cryptography
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from dataclasses import asdict
from .core import get_pqc_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/pqc", tags=["Post‑Quantum Cryptography"])

class KeypairRequest(BaseModel):
    algorithm: Optional[str] = None

class KemEncapRequest(BaseModel):
    public_key: str; algorithm: Optional[str] = None

class KemDecapRequest(BaseModel):
    secret_key: str; ciphertext: str; algorithm: Optional[str] = None

class SignRequest(BaseModel):
    secret_key: str; message: str; algorithm: Optional[str] = None

class VerifyRequest(BaseModel):
    public_key: str; message: str; signature: str; algorithm: Optional[str] = None

class HybridEncapRequest(BaseModel):
    pq_public_key: str; ecdh_public_key: str

class HybridDecapRequest(BaseModel):
    pq_secret_key: str; ecdh_secret_key: str; hybrid_ciphertext: str

@router.post("/kem/keypair")
async def kem_keypair(req: KeypairRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.kem_keypair(req.algorithm); return result

@router.post("/kem/encap")
async def kem_encap(req: KemEncapRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.kem_encap(req.public_key, req.algorithm); return result

@router.post("/kem/decap")
async def kem_decap(req: KemDecapRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.kem_decap(req.secret_key, req.ciphertext, req.algorithm); return result

@router.post("/sign/keypair")
async def sign_keypair(req: KeypairRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.sign_keypair(req.algorithm); return result

@router.post("/sign")
async def sign_message(req: SignRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.sign(req.secret_key, req.message, req.algorithm); return result

@router.post("/verify")
async def verify_signature(req: VerifyRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); valid = mgr.verify(req.public_key, req.message, req.signature, req.algorithm); return {"valid": valid}

@router.post("/hybrid/keypair")
async def hybrid_keypair(user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.hybrid_keypair(); return result

@router.post("/hybrid/encap")
async def hybrid_encap(req: HybridEncapRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.hybrid_encap(req.pq_public_key, req.ecdh_public_key); return result

@router.post("/hybrid/decap")
async def hybrid_decap(req: HybridDecapRequest, user=Depends(require_permission("admin"))):
    mgr = get_pqc_manager(); result = mgr.hybrid_decap(req.pq_secret_key, req.ecdh_secret_key, req.hybrid_ciphertext); return result
