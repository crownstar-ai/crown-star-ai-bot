# security/rbac.py – Role‑Based Access Control
from typing import List, Dict, Optional
import json
from pathlib import Path

class RBAC:
    ROLES = {
        "admin": ["*"],  # all permissions
        "user": ["chat:send", "chat:history", "modules:toggle", "models:list", "models:switch", "tier:view"],
        "viewer": ["chat:history", "modules:view", "models:list", "tier:view"],
        "auditor": ["analytics:view", "audit:view"],
        "api_client": ["chat:send", "models:list"]
    }
    
    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        perms = cls.ROLES.get(role, [])
        return "*" in perms or permission in perms
    
    @classmethod
    def get_permissions(cls, role: str) -> List[str]:
        return cls.ROLES.get(role, [])
    
    @classmethod
    def add_role(cls, role_name: str, permissions: List[str]):
        cls.ROLES[role_name] = permissions
    
    @classmethod
    def list_roles(cls) -> List[str]:
        return list(cls.ROLES.keys())
    
    @classmethod
    def check_request(cls, user_role: str, endpoint: str, method: str) -> bool:
        """Map endpoint to permission"""
        permission_map = {
            ("/v1/chat", "POST"): "chat:send",
            ("/v1/chat", "GET"): "chat:history",
            ("/v1/modules", "GET"): "modules:view",
            ("/v1/modules/", "POST"): "modules:toggle",
            ("/v1/models", "GET"): "models:list",
            ("/v1/models/", "POST"): "models:switch",
            ("/v1/tier", "GET"): "tier:view",
            ("/v1/tier", "POST"): "tier:change",
            ("/v1/analytics", "GET"): "analytics:view",
            ("/v1/audit", "GET"): "audit:view"
        }
        # Find best match
        for (path, m), perm in permission_map.items():
            if method == m and endpoint.startswith(path):
                return cls.has_permission(user_role, perm)
        # Default: allow if not restricted
        return True

# Permission constants
PERM_CHAT_SEND = "chat:send"
PERM_CHAT_HISTORY = "chat:history"
PERM_MODULES_VIEW = "modules:view"
PERM_MODULES_TOGGLE = "modules:toggle"
PERM_MODELS_LIST = "models:list"
PERM_MODELS_SWITCH = "models:switch"
PERM_TIER_VIEW = "tier:view"
PERM_TIER_CHANGE = "tier:change"
PERM_ANALYTICS_VIEW = "analytics:view"
PERM_AUDIT_VIEW = "audit:view"
PERM_ADMIN = "*"
