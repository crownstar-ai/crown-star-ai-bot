# diagnostics/api.py – REST API for mathematical verification
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import torch
import torch.nn.functional as F
import numpy as np
from src.core.crownstar_core import CrownStarCore
from src.diagnostics.model_diagnostics import get_diagnostics, ModelDiagnostics
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/diagnostics", tags=["Diagnostics"])

class JacobianRequest(BaseModel):
    input_data: List[List[float]]  # shape: batch x features (or tokens)
    output_index: Optional[int] = None

class GradientCheckRequest(BaseModel):
    input_data: List[List[float]]
    target_data: List[int]  # class labels
    epsilon: float = 1e-5

@router.post("/jacobian")
async def compute_jacobian(req: JacobianRequest, user=Depends(require_permission("admin"))):
    """Compute Jacobian of model output w.r.t input (Bishop/Yegnanarayana)."""
    core = get_core()  # would be injected
    if core.model is None:
        raise HTTPException(503, "Model not loaded")
    device = next(core.model.parameters()).device
    diag = get_diagnostics(core.model, device)
    input_tensor = torch.tensor(req.input_data, device=device, dtype=torch.float32)
    if req.output_index is not None:
        jac = diag.compute_jacobian(input_tensor, req.output_index)
    else:
        jac = diag.compute_jacobian(input_tensor)
    report = diag.jacobian_report(input_tensor)
    return {"jacobian_shape": list(jac.shape), "report": report}

@router.post("/gradient_check")
async def gradient_check(req: GradientCheckRequest, user=Depends(require_permission("admin"))):
    """Numerical vs analytical gradient check (Zurada/Bishop)."""
    core = get_core()
    if core.model is None:
        raise HTTPException(503)
    device = next(core.model.parameters()).device
    diag = get_diagnostics(core.model, device)
    input_tensor = torch.tensor(req.input_data, device=device, dtype=torch.float32)
    target_tensor = torch.tensor(req.target_data, device=device, dtype=torch.long)
    def loss_fn(out, target):
        return F.cross_entropy(out.view(-1, out.size(-1)), target.view(-1))
    reports = diag.gradient_check(loss_fn, input_tensor, target_tensor, eps=req.epsilon)
    all_passed = all(r.passed for r in reports)
    return {"passed": all_passed, "details": reports}

@router.get("/control/verify")
async def verify_control_shell(temperature: float = 0.85, min_length: int = 10, max_length: int = 512,
                               memory_context: Optional[str] = None, user=Depends(require_permission("admin"))):
    """Verify CrownStar control parameters against mathematical model."""
    core = get_core()
    diag = get_diagnostics(core.model, torch.device("cpu"))
    result = diag.verify_control_shell(temperature, min_length, max_length, memory_context)
    return result

@router.post("/full_verification")
async def full_verification(user=Depends(require_permission("admin"))):
    """Run complete verification suite: Jacobian, Hessian, gradients, control."""
    core = get_core()
    if core.model is None:
        raise HTTPException(503)
    device = next(core.model.parameters()).device
    diag = get_diagnostics(core.model, device)
    # Create dummy test data
    dummy_input = torch.randint(0, core.model.config.output_dim, (1, 16), device=device).long()
    dummy_target = torch.randint(0, core.model.config.output_dim, (1, 16), device=device).long()
    # For Jacobian we need float input – use embeddings
    with torch.no_grad():
        embedding = core.model.embedding(dummy_input)
    result = diag.full_verification(embedding, dummy_target, loss_fn=F.cross_entropy)
    return result

# Helper to get core (would be injected by app)
def get_core():
    from fastapi import Request
    # stub – real implementation uses request.app.state.core
    return None
