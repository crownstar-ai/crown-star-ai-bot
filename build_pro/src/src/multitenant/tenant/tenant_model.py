# multitenant/tenant/tenant_model.py – Tenant entity and value objects
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
import uuid
import json

@dataclass
class TenantSettings:
    """Tenant configuration (feature flags, limits, customisations)"""
    max_users: int = 100
    max_conversations_per_user: int = 10000
    allowed_models: List[str] = field(default_factory=lambda: ["deepseek_v2_lite", "gpt35"])
    custom_modules: Dict[str, bool] = field(default_factory=dict)
    rate_limit_per_user: int = 1000
    retention_days: int = 90

@dataclass
class Tenant:
    tenant_id: str
    name: str
    subdomain: Optional[str] = None
    plan: str = "free"  # free, basic, pro, enterprise
    status: str = "active"  # active, suspended, deleted
    settings: TenantSettings = field(default_factory=TenantSettings)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    @staticmethod
    def create(name: str, subdomain: str = None, plan: str = "free", created_by: str = None) -> 'Tenant':
        tenant_id = str(uuid.uuid4())[:8]
        return Tenant(
            tenant_id=tenant_id,
            name=name,
            subdomain=subdomain,
            plan=plan,
            created_by=created_by
        )
    
    def suspend(self):
        self.status = "suspended"
        self.updated_at = datetime.utcnow()
    
    def activate(self):
        self.status = "active"
        self.updated_at = datetime.utcnow()
    
    def change_plan(self, new_plan: str):
        self.plan = new_plan
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "subdomain": self.subdomain,
            "plan": self.plan,
            "status": self.status,
            "settings": {
                "max_users": self.settings.max_users,
                "max_conversations_per_user": self.settings.max_conversations_per_user,
                "allowed_models": self.settings.allowed_models,
                "rate_limit_per_user": self.settings.rate_limit_per_user,
                "retention_days": self.settings.retention_days
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata
        }

class TenantContext:
    """Thread‑local tenant context (for request scope)"""
    _local = None
    
    @classmethod
    def _get_local(cls):
        if cls._local is None:
            import threading
            cls._local = threading.local()
        return cls._local
    
    @classmethod
    def set_current_tenant(cls, tenant: Tenant):
        cls._get_local().current_tenant = tenant
    
    @classmethod
    def get_current_tenant(cls) -> Optional[Tenant]:
        return getattr(cls._get_local(), "current_tenant", None)
    
    @classmethod
    def clear(cls):
        if hasattr(cls._get_local(), "current_tenant"):
            delattr(cls._get_local(), "current_tenant")
