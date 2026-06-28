# edge/api.py – REST API for model export and deployment
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os
from .export.converter import ModelExporter, get_edge_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/edge", tags=["Edge AI"])

class ExportRequest(BaseModel):
    model_name: str = "deepseek-ai/DeepSeek-V2-Lite"
    format: str  # onnx, tflite, tensorrt

class DeployRequest(BaseModel):
    target: str  # jetson, raspberrypi, local
    model_format: str
    model_path: str

@router.post("/export")
async def export_model(req: ExportRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    """Export model to edge format (runs in background)"""
    converter = ModelExporter(model_name=req.model_name)
    output_dir = f"models/edge/{req.format}"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, req.model_name.replace("/", "_") + f".{req.format}")
    
    def export_task():
        if req.format == "onnx":
            converter.export_to_onnx(output_path)
        elif req.format == "tflite":
            converter.export_to_tflite(output_path)
        elif req.format == "tensorrt":
            onnx_path = output_path.replace(".tensorrt", ".onnx")
            converter.export_to_onnx(onnx_path)
            converter.export_to_tensorrt(onnx_path, output_path)
        else:
            raise ValueError(f"Unsupported format: {req.format}")
    
    background.add_task(export_task)
    return {"message": f"Export to {req.format} started", "output_path": output_path}

@router.get("/models")
async def list_edge_models(user: dict = Depends(require_permission("user"))):
    manager = get_edge_manager()
    models = manager.list_models()
    return {"models": models}

@router.delete("/models/{model_name}")
async def delete_edge_model(model_name: str, user: dict = Depends(require_permission("admin"))):
    manager = get_edge_manager()
    if manager.delete_model(model_name):
        return {"message": f"Model {model_name} deleted"}
    raise HTTPException(404, "Model not found")

@router.post("/deploy")
async def deploy_to_edge(req: DeployRequest, user: dict = Depends(require_permission("admin"))):
    """Trigger deployment script for specific target"""
    import subprocess
    if req.target == "jetson":
        script = "scripts/edge/deploy_jetson.sh"
    elif req.target == "raspberrypi":
        script = "scripts/edge/install_raspberrypi.sh"
    else:
        raise HTTPException(400, "Target must be jetson or raspberrypi")
    # In production, would use SSH or CI/CD
    return {"message": f"Deployment to {req.target} triggered", "script": script}

@router.get("/status")
async def edge_status(user: dict = Depends(require_permission("user"))):
    # Check edge inference server health if running
    import requests
    try:
        resp = requests.get("http://localhost:8081/v1/health", timeout=2)
        edge_ok = resp.status_code == 200
    except:
        edge_ok = False
    return {
        "edge_server_running": edge_ok,
        "exported_models": get_edge_manager().list_models(),
        "supported_formats": ["onnx", "tflite", "tensorrt"]
    }
