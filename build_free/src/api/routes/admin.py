# src/api/routes/admin.py
"""
Admin API endpoints for user and tenant management.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from src.core.logging_config import get_logger
from src.core.exceptions import NotFoundError, ForbiddenError, ValidationError
from src.database.connection import get_db_connection
from src.ddd.repositories.repositories import SQLiteUserRepository, SQLiteConversationRepository
from src.ddd.factories.factories import UserFactory
from src.ddd.value_object import Tier, ModelName

router = APIRouter()
logger = get_logger(__name__)

user_repo = SQLiteUserRepository()
conv_repo = SQLiteConversationRepository()


class CreateUserRequest(BaseModel):
    username: str
    email: str
    tier: str = "free"
    model: str = "deepseek_v2_lite"
    tenant_id: Optional[str] = None


class UpdateUserRequest(BaseModel):
    tier: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/users")
async def create_user(request: Request, req: CreateUserRequest):
    """Create a new user (admin only)."""
    # Check admin permission (simplified)
    if getattr(request.state, "tier", "free") not in ["pro", "enterprise"]:
        raise ForbiddenError("Admin access required")
    
    try:
        tier = Tier(req.tier) if req.tier else Tier.free()
        model = ModelName(req.model) if req.model else ModelName.deepseek_v2()
        user = UserFactory.create(req.username, req.email, tier, model)
        if req.tenant_id:
            # Add tenant_id (requires model extension)
            pass
        user_repo.save(user)
        logger.info(f"Admin created user: {user.id.value}")
        return {"id": user.id.value, "username": user.username, "email": user.email, "tier": user.tier.name}
    except ValueError as e:
        raise ValidationError(str(e))


@router.get("/users")
async def list_users(request: Request, limit: int = 100, offset: int = 0):
    """List all users (admin only)."""
    if getattr(request.state, "tier", "free") not in ["pro", "enterprise"]:
        raise ForbiddenError("Admin access required")
    users = user_repo.list_all(limit=limit)
    return {"users": [{"id": u.id.value, "username": u.username, "email": u.email, "tier": u.tier.name} for u in users]}


@router.get("/users/{user_id}")
async def get_user(request: Request, user_id: str):
    """Get a specific user (admin only)."""
    if getattr(request.state, "tier", "free") not in ["pro", "enterprise"]:
        raise ForbiddenError("Admin access required")
    from src.ddd.value_object import UserId
    user = user_repo.find_by_id(UserId(user_id))
    if not user:
        raise NotFoundError("User", user_id)
    return {"id": user.id.value, "username": user.username, "email": user.email, "tier": user.tier.name, "requests": user.total_requests}


@router.get("/conversations")
async def list_conversations(request: Request, user_id: Optional[str] = None, limit: int = 50):
    """List conversations (admin only)."""
    if getattr(request.state, "tier", "free") not in ["pro", "enterprise"]:
        raise ForbiddenError("Admin access required")
    if user_id:
        from src.ddd.value_object import UserId
        convs = conv_repo.find_by_user(UserId(user_id), limit)
        return {"conversations": [{"id": c.id.value, "user_id": c.user_id.value, "messages": len(c.messages)} for c in convs]}
    else:
        # List all conversations (simplified: would need a repo method)
        return {"conversations": []}
