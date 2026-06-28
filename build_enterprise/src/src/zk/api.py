# zk/api.py – REST API for zero‑knowledge proofs
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
from .core import get_zk_prover, get_zk_verifier, Proof
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/zk", tags=["Zero‑Knowledge Proofs"])

class InferenceProofRequest(BaseModel):
    model_input: Dict
    model_output: Dict
    model_hash: str

class FederatedProofRequest(BaseModel):
    old_weights_hash: str
    new_weights_hash: str
    client_id: str
    round_id: int

class VerificationRequest(BaseModel):
    proof_id: str
    proof_data: str   # base64
    verification_key_id: str

@router.post("/prove/inference")
async def prove_inference(req: InferenceProofRequest, user=Depends(require_permission("admin"))):
    """Generate ZK proof of correct inference."""
    prover = get_zk_prover()
    proof = prover.prove_inference(req.model_input, req.model_output, req.model_hash)
    if not proof:
        raise HTTPException(500, "Proof generation failed")
    return {"proof_id": proof.proof_id, "proof_data": base64.b64encode(proof.proof_data).decode(), "timestamp": proof.timestamp}

@router.post("/prove/federated")
async def prove_federated_update(req: FederatedProofRequest, user=Depends(require_permission("admin"))):
    """Generate ZK proof of correct federated update."""
    prover = get_zk_prover()
    proof = prover.prove_federated_update(req.old_weights_hash, req.new_weights_hash, req.client_id, req.round_id)
    return {"proof_id": proof.proof_id, "public_inputs": proof.public_inputs}

@router.post("/verify")
async def verify_proof(req: VerificationRequest, user=Depends(require_permission("admin"))):
    """Verify a zero‑knowledge proof."""
    import base64
    verifier = get_zk_verifier()
    proof = Proof(
        proof_id=req.proof_id,
        statement_type="inference",  # placeholder
        public_inputs={},
        proof_data=base64.b64decode(req.proof_data),
        verification_key_id=req.verification_key_id,
        timestamp=int(time.time())
    )
    result = verifier.verify(proof)
    return {"valid": result.valid, "details": result.details}

@router.get("/status")
async def zk_status(user=Depends(require_permission("admin"))):
    """Get ZK system status (keys loaded, backend ready)."""
    prover = get_zk_prover()
    return {"backend": prover.config["backend"], "keys_loaded": bool(prover.proving_keys), "proofs_dir": prover.config["proof_dir"]}
