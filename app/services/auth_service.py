from datetime import datetime, timedelta
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import (
    verify_password, 
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings
from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.services.audit_service import AuditService


class AuthService:
    """认证服务"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(session)
    
    async def authenticate(
        self, 
        username: str, 
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[User, str, str]:
        """用户认证 - 返回 (用户, access_token, refresh_token)"""
        
        # 1. 查找用户
        user = await self.user_repo.get_by_username_or_email(username)
        if not user:
            await self.audit_service.log(
                action="login_failed",
                details={"username": username, "reason": "user_not_found"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        
        # 2. 检查账户状态
        if user.status == UserStatus.LOCKED:
            if user.locked_until and user.locked_until > datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked until {user.locked_until.isoformat()}",
                )
            else:
                # 解锁
                user.status = UserStatus.ACTIVE
                user.failed_login_attempts = 0
                user.locked_until = None
                await self.session.commit()
        
        if user.status == UserStatus.INACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )
        
        # 3. 验证密码
        if not verify_password(password, user.hashed_password):
            user.failed_login_attempts += 1
            
            # 锁定账户
            if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.status = UserStatus.LOCKED
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
            
            await self.session.commit()
            
            await self.audit_service.log(
                action="login_failed",
                details={"username": username, "attempts": user.failed_login_attempts},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        
        # 4. 认证成功
        user.failed_login_attempts = 0
        user.last_login = datetime.utcnow()
        await self.session.commit()
        
        # 5. 生成令牌
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        await self.audit_service.log(
            action="login_success",
            details={"user_id": user.id, "username": user.username},
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return user, access_token, refresh_token
    
    async def refresh_token(self, refresh_token: str) -> Tuple[str, str]:
        """刷新访问令牌"""
        payload = decode_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        
        user_id = payload.get("sub")
        user = await self.user_repo.get_by_id(int(user_id))
        if not user or user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )
        
        new_access_token = create_access_token({"sub": str(user.id)})
        new_refresh_token = create_refresh_token({"sub": str(user.id)})
        
        return new_access_token, new_refresh_token