# security/advanced_middleware.py – OIDC and mTLS middleware
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from .oidc.oidc_service import get_oidc_service
from .mtls.mtls_service import get_mtls_validator
import logging

logger = logging.getLogger("crownstar.security.middleware")

class OIDCMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, skip_paths: list = None):
        super().__init__(app)
        self.skip_paths = skip_paths or ["/v1/health", "/v1/.well-known/openid-configuration", "/metrics"]
        self.oidc = get_oidc_service()
    
    async def dispatch(self, request: Request, call_next):
        # Skip public endpoints
        if any(request.url.path.startswith(p) for p in self.skip_paths):
            return await call_next(request)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = auth_header[7:]
        provider_hint = request.headers.get("X-OIDC-Provider")
        payload = self.oidc.verify_token(token, provider_hint)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        request.state.oidc_user = payload
        request.state.user_id = payload.get("sub", payload.get("user_id"))
        return await call_next(request)

class mTLSMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, require_mtls: bool = False):
        super().__init__(app)
        self.require_mtls = require_mtls
        self.validator = get_mtls_validator()
    
    async def dispatch(self, request: Request, call_next):
        if not self.require_mtls:
            return await call_next(request)
        # Get client certificate from request (provided by reverse proxy or uvicorn with ssl)
        cert = request.headers.get("X-Client-Cert")
        if not cert:
            # Try to get from uvicorn scope (if using SSL)
            scope = getattr(request, "scope", {})
            if "client_cert" in scope:
                cert = scope["client_cert"]
            else:
                raise HTTPException(status_code=401, detail="Client certificate required")
        # Decode PEM
        import base64
        try:
            cert_bytes = base64.b64decode(cert) if not cert.startswith("-----") else cert.encode()
            if isinstance(cert_bytes, bytes):
                result = self.validator.validate_certificate(cert_bytes)
            else:
                result = self.validator.validate_certificate(cert_bytes.encode())
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid certificate: {e}")
        if not result["valid"]:
            raise HTTPException(status_code=401, detail=f"Certificate validation failed: {result.get('error')}")
        request.state.client_cert_subject = result["subject"]
        return await call_next(request)
