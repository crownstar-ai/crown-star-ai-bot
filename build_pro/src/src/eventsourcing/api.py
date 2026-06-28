# eventsourcing/api.py – CQRS API
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from .commands.handlers import get_command_handler
from .projections.projections import get_projection
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/cqrs", tags=["CQRS"])

class CreateConversationRequest(BaseModel):
    user_id: str
    tier: str = "free_pay_per_use"

class AddMessageRequest(BaseModel):
    conversation_id: str
    user_message: str
    assistant_message: str
    modules_active: List[str] = []
    model: str = "deepseek_v2_lite"
    latency_ms: int = 0

class ToggleModuleRequest(BaseModel):
    module: str
    enabled: bool

class ChangeTierRequest(BaseModel):
    tier: str

class SwitchModelRequest(BaseModel):
    model: str

@router.post("/commands/create-conversation")
async def create_conversation_cmd(req: CreateConversationRequest, user: dict = Depends(require_permission("user"))):
    handler = get_command_handler()
    conv_id = handler.handle_create_conversation(req.user_id, req.tier)
    return {"conversation_id": conv_id}

@router.post("/commands/add-message")
async def add_message_cmd(req: AddMessageRequest, user: dict = Depends(require_permission("user"))):
    handler = get_command_handler()
    ok = handler.handle_add_message(req.conversation_id, req.user_message, req.assistant_message, req.modules_active, req.model, req.latency_ms)
    if not ok:
        raise HTTPException(409, "Concurrency conflict")
    return {"success": True}

@router.post("/commands/toggle-module")
async def toggle_module_cmd(req: ToggleModuleRequest, user: dict = Depends(require_permission("user"))):
    handler = get_command_handler()
    handler.handle_toggle_module(req.module, req.enabled)
    return {"success": True}

@router.post("/commands/change-tier")
async def change_tier_cmd(req: ChangeTierRequest, user: dict = Depends(require_permission("user"))):
    handler = get_command_handler()
    handler.handle_change_tier(req.tier)
    return {"success": True}

@router.post("/commands/switch-model")
async def switch_model_cmd(req: SwitchModelRequest, user: dict = Depends(require_permission("user"))):
    handler = get_command_handler()
    handler.handle_switch_model(req.model)
    return {"success": True}

@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(require_permission("user"))):
    proj = get_projection()
    conv = proj.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv

@router.get("/config")
async def get_config(user: dict = Depends(require_permission("user"))):
    proj = get_projection()
    return proj.get_config()
