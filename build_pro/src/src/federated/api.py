# federated/api.py – REST API for federated learning coordination
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from .server import get_fed_server, ModelUpdate, ClientInfo
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/federated", tags=["Federated Learning"])

class ClientRegisterRequest(BaseModel):
    client_id: str
    endpoint: str
    data_size: int
    metadata: Optional[Dict] = None

class ModelUpdateRequest(BaseModel):
    client_id: str
    round_id: int
    weights: Dict[str, List]  # serialized tensors
    num_samples: int
    metadata: Optional[Dict] = None

@router.post("/register")
async def register_client(req: ClientRegisterRequest, user=Depends(require_permission("admin"))):
    """Register a new federated learning client."""
    server = get_fed_server()
    success = server.register_client(req.client_id, req.endpoint, req.data_size, req.metadata)
    if not success:
        raise HTTPException(400, "Client already registered")
    return {"status": "registered", "client_id": req.client_id}

@router.post("/submit")
async def submit_update(req: ModelUpdateRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Submit a model update from a client (after local training)."""
    server = get_fed_server()
    # Convert serialized weights back to tensors
    import torch
    weights = {}
    for k, v_list in req.weights.items():
        weights[k] = torch.tensor(v_list)
    update = ModelUpdate(
        client_id=req.client_id,
        round_id=req.round_id,
        weights=weights,
        num_samples=req.num_samples,
        timestamp=int(time.time()),
        metadata=req.metadata or {}
    )
    server.receive_update(update)
    return {"status": "received", "round": req.round_id}

@router.post("/aggregate")
async def aggregate_round(background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Trigger aggregation of received updates (ends current round)."""
    server = get_fed_server()
    result = server.aggregate()
    return result

@router.get("/clients")
async def list_clients(user=Depends(require_permission("admin"))):
    """List all registered federated clients."""
    server = get_fed_server()
    return {"clients": server.get_client_status()}

@router.get("/model")
async def get_global_model(user=Depends(require_permission("admin"))):
    """Download current global model weights."""
    server = get_fed_server()
    return server.get_global_model()

@router.post("/round/start")
async def start_round(user=Depends(require_permission("admin"))):
    """Start a new federated training round."""
    server = get_fed_server()
    result = server.start_training_round()
    return result

@router.get("/rounds")
async def get_round_history(user=Depends(require_permission("admin"))):
    """Get history of past aggregation rounds."""
    server = get_fed_server()
    return {"rounds": server.round_history}
