# multitenant/middleware/tenant_middleware.py – FastAPI tenant resolver
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from ..tenant.tenant_model import TenantContext, Tenant
from ..tenant.tenant_repo import get_tenant_repo
import re

class TenantMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, mode: str = "header", header_name: str = "X-Tenant-Id", 
                 subdomain_regex: str = r'^([a-z0-9-]+)\.', default_tenant_id: str = None):
        super().__init__(app)
        self.mode = mode
        self.header_name = header_name
        self.subdomain_regex = subdomain_regex
        self.default_tenant_id = default_tenant_id
        self.repo = get_tenant_repo()
    
    async def dispatch(self, request: Request, call_next):
        tenant = None
        
        # Extract tenant from different sources
        if self.mode == "header":
            tenant_id = request.headers.get(self.header_name)
            if tenant_id:
                tenant = self.repo.get(tenant_id)
        elif self.mode == "subdomain":
            host = request.headers.get("host", "")
            match = re.match(self.subdomain_regex, host)
            if match:
                subdomain = match.group(1)
                tenant = self.repo.get_by_subdomain(subdomain)
        elif self.mode == "jwt":
            # Extract tenant from JWT claim (requires JWT token)
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
                try:
                    import jwt
                    payload = jwt.decode(token, options={"verify_signature": False})
                    tenant_id = payload.get("tenant_id")
                    if tenant_id:
                        tenant = self.repo.get(tenant_id)
                except:
                    pass
        
        # Fallback to default
        if not tenant and self.default_tenant_id:
            tenant = self.repo.get(self.default_tenant_id)
        
        if not tenant:
            # Allow health endpoints to bypass tenant
            if request.url.path in ["/v1/health", "/metrics", "/ready", "/live"]:
                return await call_next(request)
            raise HTTPException(status_code=400, detail="Tenant not found or not specified")
        
        # Check tenant status
        if tenant.status != "active":
            raise HTTPException(status_code=403, detail="Tenant is suspended or inactive")
        
        # Set tenant context for this request
        TenantContext.set_current_tenant(tenant)
        
        response = await call_next(request)
        TenantContext.clear()
        return response
