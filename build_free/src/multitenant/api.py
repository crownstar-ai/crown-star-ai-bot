# multitenant/api.py – REST API for tenant administration
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from .tenant.tenant_model import Tenant, TenantSettings
from .tenant.tenant_repo import get_tenant_repo
from .middleware.tenant_middleware import TenantContext
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/tenants", tags=["Tenant Management"])

class CreateTenantRequest(BaseModel):
    name: str
    subdomain: Optional[str] = None
    plan: str = "free"

class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    subdomain: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None

class AddUserToTenantRequest(BaseModel):
    user_id: str
    role: str = "member"  # member, admin

@router.post("/")
async def create_tenant(req: CreateTenantRequest, user: dict = Depends(require_permission("admin"))):
    repo = get_tenant_repo()
    existing = repo.get_by_name(req.name)
    if existing:
        raise HTTPException(400, "Tenant name already exists")
    if req.subdomain:
        existing_sub = repo.get_by_subdomain(req.subdomain)
        if existing_sub:
            raise HTTPException(400, "Subdomain already taken")
    tenant = Tenant.create(req.name, req.subdomain, req.plan, user.get("user_id"))
    repo.save(tenant)
    return {"tenant": tenant.to_dict()}

@router.get("/")
async def list_tenants(limit: int = 100, user: dict = Depends(require_permission("admin"))):
    repo = get_tenant_repo()
    tenants = repo.list_all(limit)
    return {"tenants": [t.to_dict() for t in tenants]}

@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, user: dict = Depends(require_permission("admin"))):
    repo = get_tenant_repo()
    tenant = repo.get(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant.to_dict()

@router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, req: UpdateTenantRequest, user: dict = Depends(require_permission("admin"))):
    repo = get_tenant_repo()
    tenant = repo.get(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if req.name:
        tenant.name = req.name
    if req.subdomain:
        tenant.subdomain = req.subdomain
    if req.plan:
        tenant.plan = req.plan
    if req.status:
        tenant.status = req.status
    tenant.updated_at = datetime.utcnow()
    repo.save(tenant)
    return tenant.to_dict()

@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, user: dict = Depends(require_permission("admin"))):
    repo = get_tenant_repo()
    if repo.delete(tenant_id):
        return {"message": "Tenant deleted"}
    raise HTTPException(404, "Tenant not found")

@router.get("/current/switch")
async def switch_tenant(tenant_id: str, user: dict = Depends(require_permission("user"))):
    """Switch current user's active tenant (store in session/token)"""
    repo = get_tenant_repo()
    tenant = repo.get(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    # In real implementation, update user's JWT or session
    return {"tenant_id": tenant_id, "message": "Switched tenant"}

@router.post("/{tenant_id}/users")
async def add_user_to_tenant(tenant_id: str, req: AddUserToTenantRequest, user: dict = Depends(require_permission("admin"))):
    repo = get_tenant_repo()
    tenant = repo.get(tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    # Update user's tenant_id in users table
    import sqlite3
    conn = sqlite3.connect("data/security/users.db")
    conn.execute("UPDATE users SET tenant_id = ? WHERE user_id = ?", (tenant_id, req.user_id))
    conn.commit()
    conn.close()
    return {"user_id": req.user_id, "tenant_id": tenant_id, "role": req.role}

@router.get("/{tenant_id}/users")
async def list_tenant_users(tenant_id: str, user: dict = Depends(require_permission("admin"))):
    import sqlite3
    conn = sqlite3.connect("data/security/users.db")
    cur = conn.execute("SELECT user_id, username, email, role FROM users WHERE tenant_id = ?", (tenant_id,))
    users = [{"user_id": r[0], "username": r[1], "email": r[2], "role": r[3]} for r in cur.fetchall()]
    conn.close()
    return {"users": users}

from datetime import datetime
