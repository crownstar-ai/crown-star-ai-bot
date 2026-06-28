# functions/api.py – REST API for edge functions
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_fn_manager, FunctionDefinition, FunctionRuntime
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/functions", tags=["Edge Functions"])

class DeployRequest(BaseModel):
    name: str; runtime: str; code: str; entrypoint: str; triggers: List[Dict]
    memory_mb: Optional[int] = None; timeout_seconds: Optional[int] = None

class InvokeRequest(BaseModel):
    event: Dict = {}; context: Dict = {}

class KVRequest(BaseModel):
    namespace: str; key: str; value: Any

@router.post("/deploy")
async def deploy_function(req: DeployRequest, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    func_id = mgr.deploy(name=req.name, runtime=req.runtime, code=req.code, entrypoint=req.entrypoint, triggers=req.triggers, memory_mb=req.memory_mb, timeout_seconds=req.timeout_seconds)
    return {"function_id": func_id, "status": "deployed"}

@router.post("/{function_id}/invoke")
async def invoke_function(function_id: str, req: InvokeRequest, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    result = mgr.invoke_function(function_id, req.event, req.context)
    return result

@router.get("/{function_id}")
async def get_function(function_id: str, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    func = mgr.get_function(function_id)
    if not func: raise HTTPException(404, "Function not found")
    return asdict(func)

@router.get("/")
async def list_functions(user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    funcs = mgr.list_functions()
    return {"functions": [asdict(f) for f in funcs]}

@router.delete("/{function_id}")
async def delete_function(function_id: str, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    success = mgr.delete_function(function_id)
    if not success: raise HTTPException(404, "Function not found")
    return {"status": "deleted"}

@router.get("/logs")
async def get_logs(function_id: Optional[str] = None, limit: int = 100, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    logs = mgr.get_logs(function_id, limit)
    return {"logs": logs}

@router.post("/kv/{function_id}/{namespace}/{key}")
async def kv_put(function_id: str, namespace: str, key: str, req: KVRequest, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    mgr.kv_put(namespace, key, req.value, function_id)
    return {"status": "stored"}

@router.get("/kv/{function_id}/{namespace}/{key}")
async def kv_get(function_id: str, namespace: str, key: str, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    value = mgr.kv_get(namespace, key, function_id)
    if value is None: raise HTTPException(404, "Key not found")
    return {"value": value}

@router.delete("/kv/{function_id}/{namespace}/{key}")
async def kv_delete(function_id: str, namespace: str, key: str, user=Depends(require_permission("admin"))):
    mgr = get_fn_manager()
    success = mgr.kv_delete(namespace, key, function_id)
    if not success: raise HTTPException(404, "Key not found")
    return {"status": "deleted"}
