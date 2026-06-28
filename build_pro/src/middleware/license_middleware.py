import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from licensing.license_manager import LicenseManager

class LicenseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, license_key=None):
        super().__init__(app)
        self.license_key = license_key or os.environ.get("CROWNSTAR_LICENSE_KEY")
        self.license_manager = LicenseManager()
        self.public_paths = ["/v1/health", "/v1/metrics", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in self.public_paths):
            return await call_next(request)
        if not self.license_key:
            request.state.tier = "free"
            return await call_next(request)
        valid = self.license_manager.validate_license(self.license_key)
        if not valid:
            raise HTTPException(status_code=403, detail="Invalid or expired license")
        payload = self.license_manager.decode_license(self.license_key)
        if payload:
            request.state.tier = payload.get("tier", "basic")
            request.state.license_email = payload.get("email")
        return await call_next(request)
