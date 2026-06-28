# ddd/api.py – REST API for DDD entities
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from .value_object import UserId, ConversationId, Tier, ModelName, Money
from .entities.domain_entities import User, Conversation
from .repositories.repositories import SQLiteUserRepository, SQLiteConversationRepository, SQLiteModuleConfigurationRepository
from .services.domain_services import PricingService, ConversationService, UserRegistrationService, ModuleActivationService
from .factories.factories import UserFactory, ConversationFactory
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/ddd", tags=["Domain‑Driven Design"])

# Repository instances
user_repo = SQLiteUserRepository()
conv_repo = SQLiteConversationRepository()
config_repo = SQLiteModuleConfigurationRepository()
pricing = PricingService()
conv_service = ConversationService(conv_repo, user_repo, pricing)
user_reg = UserRegistrationService(user_repo)
module_activation = ModuleActivationService(config_repo, user_repo)

class CreateUserRequest(BaseModel):
    username: str
    email: str
    tier: Optional[str] = "free_pay_per_use"

class CreateConversationRequest(BaseModel):
    user_id: str

class AddMessageRequest(BaseModel):
    conversation_id: str
    user_id: str
    user_message: str
    assistant_message: str
    modules_active: List[str] = []
    model: str = "deepseek_v2_lite"
    latency_ms: int = 0

class ToggleGlobalModuleRequest(BaseModel):
    module: str
    enabled: bool

@router.post("/users")
async def create_user(req: CreateUserRequest, user: dict = Depends(require_permission("admin"))):
    try:
        tier = Tier(req.tier)
        new_user = user_reg.register(req.username, req.email, tier)
        return {"user_id": new_user.id.value, "username": new_user.username, "tier": new_user.tier.name}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/users/{user_id}")
async def get_user(user_id: str, user: dict = Depends(require_permission("user"))):
    u = user_repo.find_by_id(UserId(user_id))
    if not u:
        raise HTTPException(404, "User not found")
    return {"id": u.id.value, "username": u.username, "email": u.email, "tier": u.tier.name, "total_requests": u.total_requests, "total_cost": u.total_cost.amount}

@router.get("/users")
async def list_users(limit: int = 50, user: dict = Depends(require_permission("admin"))):
    users = user_repo.list_all(limit)
    return {"users": [{"id": u.id.value, "username": u.username, "tier": u.tier.name} for u in users]}

@router.post("/conversations")
async def create_conversation(req: CreateConversationRequest, user: dict = Depends(require_permission("user"))):
    u = user_repo.find_by_id(UserId(req.user_id))
    if not u:
        raise HTTPException(404, "User not found")
    conv = ConversationFactory.create(u.id, u.tier)
    conv_repo.save(conv)
    return {"conversation_id": conv.id.value}

@router.post("/conversations/message")
async def add_message(req: AddMessageRequest, user: dict = Depends(require_permission("user"))):
    conv_id = ConversationId(req.conversation_id)
    user_id = UserId(req.user_id)
    success = conv_service.add_message(conv_id, user_id, req.user_message, req.assistant_message, req.modules_active, req.model, req.latency_ms)
    if not success:
        raise HTTPException(404, "Conversation or user not found")
    return {"success": True}

@router.get("/conversations/{user_id}")
async def list_conversations(user_id: str, limit: int = 20, user: dict = Depends(require_permission("user"))):
    convs = conv_service.get_user_conversations(UserId(user_id), limit)
    return {"conversations": [{"id": c.id.value, "message_count": c.message_count(), "updated_at": c.updated_at.isoformat()} for c in convs]}

@router.post("/modules/global/toggle")
async def toggle_global_module(req: ToggleGlobalModuleRequest, user: dict = Depends(require_permission("admin"))):
    config = module_activation.toggle_global_module(req.module, req.enabled)
    return {"module": req.module, "enabled": req.enabled, "version": config.version}

@router.get("/config")
async def get_config(user: dict = Depends(require_permission("user"))):
    config = config_repo.get()
    return {"modules": config.modules, "version": config.version}

@router.get("/pricing")
async def get_pricing(user: dict = Depends(require_permission("user"))):
    return {"tiers": PricingService.TIER_RATES}
