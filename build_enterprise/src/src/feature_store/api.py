# feature_store/api.py – REST API for real‑time feature store
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_fs_manager, FeatureDefinition, EntityDefinition, ValueType, FeatureQuery
from security.dependencies import require_permission
import time

router = APIRouter(prefix="/v1/featurestore", tags=["Feature Store"])

class RegisterFeatureRequest(BaseModel):
    name: str; value_type: str; description: str = ""; source: str = "batch"; ttl_seconds: Optional[int] = 86400
class RegisterEntityRequest(BaseModel):
    name: str; join_key: str; description: str = ""
class SetFeatureRequest(BaseModel):
    feature_name: str; entity_key: str; value: Any; timestamp: Optional[int] = None
class OnlineQueryRequest(BaseModel):
    feature_names: List[str]; entity_keys: List[str]; entity_join_key: str
class OfflineExportRequest(BaseModel):
    feature_names: List[str]; start_time: int; end_time: int

@router.post("/features/register")
async def register_feature(req: RegisterFeatureRequest, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    fdef = FeatureDefinition(name=req.name, value_type=ValueType(req.value_type), description=req.description, source=req.source, ttl_seconds=req.ttl_seconds)
    mgr.register_feature(fdef)
    return {"status": "registered", "feature": req.name}

@router.post("/entities/register")
async def register_entity(req: RegisterEntityRequest, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    edef = EntityDefinition(name=req.name, join_key=req.join_key, description=req.description)
    mgr.register_entity(edef)
    return {"status": "registered", "entity": req.name}

@router.get("/features")
async def list_features(user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    return {"features": [{"name": n, "value_type": f.value_type.value, "source": f.source} for n,f in mgr.feature_defs.items()]}

@router.post("/set")
async def set_feature(req: SetFeatureRequest, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    success = mgr.set_feature(req.feature_name, req.entity_key, req.value, req.timestamp)
    if not success: raise HTTPException(500, "Failed to set feature")
    return {"status": "set", "feature": req.feature_name, "entity": req.entity_key}

@router.get("/get/{feature_name}/{entity_key}")
async def get_feature(feature_name: str, entity_key: str, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    value = mgr.get_feature(feature_name, entity_key)
    if value is None: raise HTTPException(404, "Feature not found")
    return {"feature": feature_name, "entity": entity_key, "value": value}

@router.post("/online")
async def online_query(req: OnlineQueryRequest, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    query = FeatureQuery(feature_names=req.feature_names, entity_keys=req.entity_keys, entity_join_key=req.entity_join_key)
    df = mgr.get_online_features(query)
    return {"results": df.to_dict(orient="records")}

@router.post("/offline/export")
async def export_offline(req: OfflineExportRequest, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    from datetime import datetime
    df = mgr.export_training_data(req.feature_names, datetime.fromtimestamp(req.start_time), datetime.fromtimestamp(req.end_time))
    return {"training_data": df.to_dict(orient="records"), "row_count": len(df)}

@router.get("/stats/{feature_name}")
async def feature_stats(feature_name: str, user=Depends(require_permission("admin"))):
    mgr = get_fs_manager()
    return mgr.get_feature_stats(feature_name)
