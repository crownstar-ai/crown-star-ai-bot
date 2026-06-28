# scaling/api.py – REST endpoints for auto‑scaling and cost optimization
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Optional
from .predictive.predictive_scaler import get_predictive_scaler
from .cost.cost_optimizer import get_cost_optimizer
from .cost.spot_handler import get_spot_handler
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/scaling", tags=["Auto‑Scaling"])

@router.get("/predict")
async def get_prediction(user: dict = Depends(require_permission("admin"))):
    scaler = get_predictive_scaler()
    return scaler.get_recommendation()

@router.post("/predict/apply")
async def apply_prediction(user: dict = Depends(require_permission("admin"))):
    scaler = get_predictive_scaler()
    result = scaler.apply_recommendation()
    return result

@router.get("/cost/optimize")
async def get_cost_optimization(user: dict = Depends(require_permission("admin"))):
    optimizer = get_cost_optimizer()
    return optimizer.generate_optimization_report()

@router.post("/cost/rightsize")
async def apply_rightsizing(user: dict = Depends(require_permission("admin"))):
    optimizer = get_cost_optimizer()
    # Simulate applying rightsizing
    return {"message": "Rightsizing recommendation applied (simulated)"}

@router.get("/spot/status")
async def spot_status(user: dict = Depends(require_permission("admin"))):
    handler = get_spot_handler()
    return {
        "interruption_notified": handler.is_interrupted(),
        "handlers_installed": handler._hook_installed
    }

@router.post("/spot/install")
async def install_spot_handlers(user: dict = Depends(require_permission("admin"))):
    handler = get_spot_handler()
    handler.install_handlers()
    return {"message": "Spot handlers installed"}
