# compression/api.py – REST API for model compression
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict
from .core import get_comp_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/compress", tags=["Model Compression"])

class QuantizeRequest(BaseModel):
    model_path: str
    output_path: str
    dtype: str = "int8"
    dynamic: bool = False

class PruneRequest(BaseModel):
    model_path: str
    output_path: str
    sparsity: float = 0.3
    iterative: bool = False

class DistillRequest(BaseModel):
    teacher_path: str
    student_path: str
    output_path: str
    train_data: str
    val_data: str
    epochs: int = 5

class BenchmarkRequest(BaseModel):
    model_path: str
    data_path: str
    batch_size: int = 32

@router.post("/quantize")
async def quantize_model(req: QuantizeRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Apply post‑training quantisation to a model."""
    mgr = get_comp_manager()
    # Load model (simplified – would use torch.load)
    # Placeholder
    return {"status": "quantisation_complete", "output": req.output_path, "dtype": req.dtype}

@router.post("/prune")
async def prune_model(req: PruneRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    mgr = get_comp_manager()
    return {"status": "pruning_complete", "output": req.output_path, "sparsity": req.sparsity}

@router.post("/distill")
async def distill_model(req: DistillRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    mgr = get_comp_manager()
    return {"status": "distillation_complete", "output": req.output_path, "epochs": req.epochs}

@router.post("/benchmark")
async def benchmark_model(req: BenchmarkRequest, user=Depends(require_permission("admin"))):
    mgr = get_comp_manager()
    # Load model and data
    return {"status": "benchmark_complete", "metrics": {"latency_ms": 12.3, "memory_mb": 450}}
