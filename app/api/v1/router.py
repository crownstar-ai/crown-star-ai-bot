from fastapi import APIRouter
from app.api.v1.endpoints import auth, chat, admin, health, users

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(health.router, prefix="/health", tags=["health"])
