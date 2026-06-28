# xai/api.py – REST API for Explainable AI
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_xai_manager, ExplanationType
from security.dependencies import require_permission
import json, numpy as np, torch

router = APIRouter(prefix="/v1/xai", tags=["Explainable AI"])

class SHAPRequest(BaseModel):
    model_id: str
    version_id: str
    input_data: List[List[float]]
    feature_names: Optional[List[str]] = None

class LIMERequest(BaseModel):
    model_id: str
    version_id: str
    input_instance: List[float]
    feature_names: Optional[List[str]] = None

class IGRequest(BaseModel):
    model_id: str
    version_id: str
    input_tensor: List[List[float]]
    target_class: Optional[int] = None

@router.post("/shap")
async def shap_explain(req: SHAPRequest, user=Depends(require_permission("admin"))):
    mgr = get_xai_manager()
    model = None
    input_np = np.array(req.input_data)
    explanation = mgr.explain_shap(model, input_np, req.model_id, req.version_id, req.feature_names)
    vis_b64 = mgr.visualise_shap(explanation)
    return {"explanation_id": explanation.explanation_id, "visualisation_base64": vis_b64, "importances": [asdict(i) for i in explanation.feature_importances]}

@router.post("/lime")
async def lime_explain(req: LIMERequest, user=Depends(require_permission("admin"))):
    mgr = get_xai_manager()
    model = None
    input_np = np.array(req.input_instance)
    explanation = mgr.explain_lime(model, input_np, req.model_id, req.version_id, req.feature_names)
    return {"explanation_id": explanation.explanation_id, "importances": [asdict(i) for i in explanation.feature_importances]}

@router.post("/integrated_gradients")
async def integrated_gradients_explain(req: IGRequest, user=Depends(require_permission("admin"))):
    mgr = get_xai_manager()
    model = None
    input_tensor = torch.tensor(req.input_tensor, dtype=torch.float32)
    explanation = mgr.explain_integrated_gradients(model, input_tensor, req.target_class, req.model_id, req.version_id)
    return {"explanation_id": explanation.explanation_id, "attributions": [asdict(i) for i in explanation.feature_importances[:100]]}

@router.get("/explanation/{exp_id}")
async def get_explanation(exp_id: str, user=Depends(require_permission("admin"))):
    mgr = get_xai_manager()
    exp = mgr.get_explanation(exp_id)
    if not exp:
        raise HTTPException(404, "Explanation not found")
    return asdict(exp)
