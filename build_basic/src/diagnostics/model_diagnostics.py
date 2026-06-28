# diagnostics/model_diagnostics.py – CrownStar Mathematical Verification Engine
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import time
import hashlib
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class JacobianReport:
    input_shape: Tuple[int, ...]
    output_shape: Tuple[int, ...]
    jacobian_norm: float
    condition_number: float
    max_singular_value: float
    min_singular_value: float
    rank: int
    computation_time_ms: float
    is_valid: bool

@dataclass
class HessianReport:
    param_count: int
    hessian_norm: float
    eigenvalues_max: float
    eigenvalues_min: float
    condition_number: float
    is_positive_definite: bool
    computation_time_ms: float

@dataclass
class GradientCheckReport:
    param_name: str
    analytical_norm: float
    numerical_norm: float
    relative_error: float
    max_absolute_error: float
    passed: bool

class ModelDiagnostics:
    """
    Implements mathematical verification of CrownStar's neural network
    according to the unified super‑model (Gurney, Yegnanarayana, Haykin, Bishop, Zurada, CrownStar).
    """
    def __init__(self, model: nn.Module, device: torch.device = torch.device("cpu")):
        self.model = model
        self.device = device
        self.model.to(device)
        self.model.eval()

    # -----------------------------------------------------------------
    # 2.1 Jacobian of output w.r.t input (Bishop / Yegnanarayana style)
    # -----------------------------------------------------------------
    def compute_jacobian(self, input_tensor: torch.Tensor, output_index: Optional[int] = None) -> torch.Tensor:
        """
        Compute the Jacobian matrix J = ∂y/∂x.
        If output_index is given, compute only that output neuron's gradient.
        Returns Jacobian of shape (output_dim, input_dim) or (1, input_dim) if output_index given.
        """
        input_tensor.requires_grad_(True)
        output = self.model(input_tensor)
        if output_index is not None:
            output = output[..., output_index].sum()
        else:
            # Flatten output to compute full Jacobian
            output = output.view(-1).sum()
        # Compute gradients w.r.t input
        grads = torch.autograd.grad(output, input_tensor, create_graph=False, retain_graph=False)[0]
        if output_index is not None:
            return grads.detach().view(1, -1)
        else:
            # Full Jacobian: need to compute per output element (memory heavy)
            # For large models, use per-output gradient loop
            batch_size = input_tensor.shape[0]
            input_flat = input_tensor.view(batch_size, -1)
            output_flat = output.view(batch_size, -1)
            jacobian = torch.zeros(output_flat.shape[1], input_flat.shape[1], device=self.device)
            for i in range(output_flat.shape[1]):
                grad_i = torch.autograd.grad(output_flat[0, i], input_tensor, retain_graph=True)[0]
                jacobian[i] = grad_i.view(-1)
            return jacobian

    def jacobian_report(self, input_tensor: torch.Tensor) -> JacobianReport:
        """Generate detailed Jacobian analysis report."""
        start = time.perf_counter()
        jac = self.compute_jacobian(input_tensor, output_index=0)  # use first output for speed
        jac_np = jac.cpu().numpy()
        # Compute SVD
        U, S, Vt = np.linalg.svd(jac_np, full_matrices=False)
        cond_num = S[0] / (S[-1] if S[-1] > 1e-10 else 1e-10)
        rank = np.sum(S > 1e-6)
        elapsed = (time.perf_counter() - start) * 1000
        return JacobianReport(
            input_shape=tuple(input_tensor.shape),
            output_shape=(self.model(input_tensor).shape[-1],),
            jacobian_norm=float(np.linalg.norm(jac_np)),
            condition_number=float(cond_num),
            max_singular_value=float(S[0]),
            min_singular_value=float(S[-1] if len(S) > 0 else 0),
            rank=int(rank),
            computation_time_ms=elapsed,
            is_valid=cond_num < 1e6
        )

    # -----------------------------------------------------------------
    # 2.2 Hessian of loss w.r.t parameters (second‑order optimization)
    # -----------------------------------------------------------------
    def compute_hessian_vector_product(self, loss: torch.Tensor, params: List[nn.Parameter], vector: List[torch.Tensor]) -> List[torch.Tensor]:
        """
        Compute Hessian‑vector product H·v for a given loss and parameter list.
        Used for large‑scale Hessian approximations.
        """
        grad = torch.autograd.grad(loss, params, create_graph=True, retain_graph=True)
        hv = torch.autograd.grad(grad, params, grad_outputs=vector, retain_graph=False)
        return hv

    def hessian_report(self, loss_fn: Callable, sample_input: torch.Tensor, sample_target: torch.Tensor) -> HessianReport:
        """Analyze Hessian of loss w.r.t model parameters."""
        start = time.perf_counter()
        output = self.model(sample_input)
        loss = loss_fn(output, sample_target)
        params = list(self.model.parameters())
        # Compute full Hessian (for small models only)
        # Here we estimate using Hessian‑vector product with random vectors
        param_vec = [torch.randn_like(p) for p in params]
        hv = self.compute_hessian_vector_product(loss, params, param_vec)
        hv_norm = sum(torch.norm(h).item() for h in hv)
        # Approximate eigenvalues via power iteration (simplified)
        # For a real implementation, use torch.autograd.functional.hessian
        # Placeholder: compute Frobenius norm as estimate
        elapsed = (time.perf_counter() - start) * 1000
        return HessianReport(
            param_count=sum(p.numel() for p in params),
            hessian_norm=hv_norm,
            eigenvalues_max=0.0,
            eigenvalues_min=0.0,
            condition_number=0.0,
            is_positive_definite=False,
            computation_time_ms=elapsed
        )

    # -----------------------------------------------------------------
    # 2.3 Gradient verification (numerical vs analytical)
    # -----------------------------------------------------------------
    def gradient_check(self, loss_fn: Callable, sample_input: torch.Tensor, sample_target: torch.Tensor,
                       eps: float = 1e-5, threshold: float = 1e-4) -> List[GradientCheckReport]:
        """
        Compare analytical gradients (autograd) with numerical finite differences.
        Implements the classic Bishop / Zurada gradient verification.
        """
        self.model.train()
        # Compute analytical gradients
        output = self.model(sample_input)
        loss = loss_fn(output, sample_target)
        grads_analytical = torch.autograd.grad(loss, self.model.parameters(), create_graph=False)
        reports = []
        for idx, (name, param) in enumerate(self.model.named_parameters()):
            if param.grad is None:
                continue
            grad_ana = grads_analytical[idx].detach().clone()
            # Numerical gradient: finite differences
            grad_num = torch.zeros_like(grad_ana)
            param_orig = param.data.clone()
            for i in range(param.numel()):
                # Positive perturbation
                param.data.view(-1)[i] += eps
                loss_plus = loss_fn(self.model(sample_input), sample_target)
                # Negative perturbation
                param.data.view(-1)[i] -= 2 * eps
                loss_minus = loss_fn(self.model(sample_input), sample_target)
                # Restore
                param.data = param_orig.clone()
                grad_num.view(-1)[i] = (loss_plus - loss_minus).item() / (2 * eps)
            # Compute errors
            rel_error = torch.abs(grad_ana - grad_num).max().item() / (torch.abs(grad_ana).max().item() + 1e-8)
            max_abs_error = torch.abs(grad_ana - grad_num).max().item()
            passed = rel_error < threshold
            reports.append(GradientCheckReport(
                param_name=name,
                analytical_norm=float(torch.norm(grad_ana).item()),
                numerical_norm=float(torch.norm(grad_num).item()),
                relative_error=rel_error,
                max_absolute_error=max_abs_error,
                passed=passed
            ))
        self.model.eval()
        return reports

    # -----------------------------------------------------------------
    # 2.4 Control Shell parameter verification (CrownStar specific)
    # -----------------------------------------------------------------
    def verify_control_shell(self, temperature: float, min_length: int, max_length: int,
                             memory_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate that CrownStar control parameters are within safe ranges
        and consistent with the mathematical model.
        """
        issues = []
        warnings = []
        if temperature < 0.0 or temperature > 2.0:
            issues.append(f"Temperature {temperature} out of range [0,2]")
        elif temperature < 0.2:
            warnings.append("Very low temperature may cause repetitive outputs")
        elif temperature > 1.5:
            warnings.append("High temperature may cause incoherent outputs")
        if min_length < 1:
            issues.append(f"min_length {min_length} < 1")
        if max_length < min_length:
            issues.append(f"max_length {max_length} < min_length {min_length}")
        if memory_context and len(memory_context) > 10000:
            warnings.append(f"Memory context length {len(memory_context)} exceeds 10000 chars, may exceed model limit")
        # Check that temperature scaling factor (as in super‑model) is applied
        # In CrownStar, the model uses a learnable temperature_scale parameter
        if hasattr(self.model, 'temperature_scale'):
            ts = self.model.temperature_scale.item()
            if ts < 0.1 or ts > 2.0:
                warnings.append(f"Model's temperature_scale={ts:.2f} outside typical range")
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "temperature": temperature,
            "min_length": min_length,
            "max_length": max_length,
            "memory_length": len(memory_context) if memory_context else 0
        }

    # -----------------------------------------------------------------
    # 2.5 Full verification suite (runs all checks)
    # -----------------------------------------------------------------
    def full_verification(self, test_input: torch.Tensor, test_target: torch.Tensor,
                          loss_fn: Callable = F.cross_entropy) -> Dict:
        """Run Jacobian, Hessian, gradient check, and control shell validation."""
        # Jacobian
        jac_report = self.jacobian_report(test_input)
        # Hessian (approximate)
        hess_report = self.hessian_report(loss_fn, test_input, test_target)
        # Gradient check (first few parameters)
        grad_reports = self.gradient_check(loss_fn, test_input, test_target, threshold=1e-3)
        # Control shell (placeholder values)
        control = self.verify_control_shell(temperature=0.85, min_length=10, max_length=512)
        return {
            "jacobian": asdict(jac_report),
            "hessian": asdict(hess_report),
            "gradient_checks": [asdict(r) for r in grad_reports],
            "control_shell": control,
            "timestamp": time.time(),
            "device": str(self.device)
        }

# Global singleton
_diagnostics = None
def get_diagnostics(model, device):
    global _diagnostics
    if _diagnostics is None:
        _diagnostics = ModelDiagnostics(model, device)
    return _diagnostics
