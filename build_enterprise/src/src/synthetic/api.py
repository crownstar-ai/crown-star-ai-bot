# synthetic/api.py – REST API for synthetic data generation and test data versions
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
from .service import get_synth, get_data_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/synthetic", tags=["Synthetic Data"])

class GenerateRequest(BaseModel):
    schema_name: str  # user, conversation, metric, or custom JSON
    count: int = 10
    custom_schema: Optional[Dict] = None

class VersionRequest(BaseModel):
    name: str
    data: Any
    metadata: Optional[Dict] = None

@router.post("/generate")
async def generate_data(req: GenerateRequest, user: dict = Depends(require_permission("admin"))):
    synth = get_synth()
    if req.custom_schema:
        schema = req.custom_schema
    else:
        schema_path = f"src/synthetic/schemas/{req.schema_name}.json"
        try:
            with open(schema_path, "r") as f:
                schema = json.load(f)
        except FileNotFoundError:
            raise HTTPException(404, f"Schema '{req.schema_name}' not found")
    
    data = synth.generate_list(schema, req.count)
    return {"count": len(data), "data": data}

@router.post("/generate/conversations")
async def generate_conversations(count: int = 50, user_id: str = "test_user", user: dict = Depends(require_permission("admin"))):
    synth = get_synth()
    with open("src/synthetic/schemas/conversation.json", "r") as f:
        schema = json.load(f)
    # Override user_id
    convs = []
    for _ in range(count):
        conv = synth.generate_object(schema)
        conv["user_id"] = user_id
        convs.append(conv)
    return {"conversations": convs}

@router.post("/version/create")
async def create_version(req: VersionRequest, user: dict = Depends(require_permission("admin"))):
    mgr = get_data_manager()
    mgr.create_version(req.name, req.data, req.metadata)
    return {"version": req.name, "message": "created"}

@router.get("/version/list")
async def list_versions(user: dict = Depends(require_permission("admin"))):
    mgr = get_data_manager()
    versions = mgr.list_versions()
    return {"versions": versions}

@router.get("/version/{name}")
async def get_version(name: str, user: dict = Depends(require_permission("admin"))):
    mgr = get_data_manager()
    version = mgr.load_version(name)
    if not version:
        raise HTTPException(404, "Version not found")
    return version

@router.delete("/version/{name}")
async def delete_version(name: str, user: dict = Depends(require_permission("admin"))):
    mgr = get_data_manager()
    if mgr.delete_version(name):
        return {"message": f"Version {name} deleted"}
    raise HTTPException(404, "Version not found")

@router.post("/version/restore/{name}")
async def restore_version(name: str, target_path: str = None, user: dict = Depends(require_permission("admin"))):
    mgr = get_data_manager()
    data = mgr.restore_version(name, target_path)
    if data is None:
        raise HTTPException(404, "Version not found")
    return {"message": f"Restored version {name}", "data_preview": str(data)[:500]}

@router.get("/schema/list")
async def list_schemas(user: dict = Depends(require_permission("user"))):
    import glob
    schemas = [p.stem for p in glob.glob("src/synthetic/schemas/*.json")]
    return {"schemas": schemas}
