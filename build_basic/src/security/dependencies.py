# security/dependencies.py – FastAPI security dependencies
from fastapi import HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import json
from .jwt import verify_token
from .api_keys import APIKeyManager
from .users import UserManager
from .rbac import RBAC

security = HTTPBearer(auto_error=False)
api_key_manager = None
user_manager = None

def init_security():
    global api_key_manager, user_manager
    if api_key_manager is None:
        api_key_manager = APIKeyManager()
    if user_manager is None:
        user_manager = UserManager()

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None)
):
    """Extract user from JWT or API key"""
    init_security()
    
    # Try JWT Bearer token first
    if credentials:
        payload = verify_token(credentials.credentials)
        if payload:
            user = user_manager.get_user(payload["sub"])
            if user:
                return user
    
    # Then try API key
    if x_api_key:
        key_info = api_key_manager.validate_key(x_api_key)
        if key_info:
            # Create virtual user from API key
            return {
                "user_id": key_info["user_id"],
                "username": f"api_{key_info['user_id'][:8]}",
                "email": "",
                "role": "api_client",
                "is_api_key": True,
                "scopes": key_info["scopes"]
            }
    
    raise HTTPException(status_code=401, detail="Not authenticated")

async def require_permission(permission: str, user: dict = Depends(get_current_user)):
    role = user.get("role", "user")
    if not RBAC.has_permission(role, permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
    return user

async def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None)
):
    try:
        return await get_current_user(None, credentials, x_api_key)
    except HTTPException:
        return {"user_id": "anonymous", "role": "viewer", "is_anonymous": True}
