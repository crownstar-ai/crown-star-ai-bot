# apiversioning/middleware/version_middleware.py – Version negotiation
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import re
from ..version_registry import get_version_registry, VersionStatus

class VersionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, strategy: str = "path", version_header: str = "X-API-Version",
                 accept_header_regex: str = r'application/vnd\.crownstar\.v(\d+)\+json'):
        super().__init__(app)
        self.strategy = strategy
        self.version_header = version_header
        self.accept_header_regex = accept_header_regex
        self.registry = get_version_registry()
    
    async def dispatch(self, request: Request, call_next):
        # Extract requested version
        requested_version = None
        
        # Strategy 1: URI path (e.g., /v1/chat)
        if self.strategy == "path" or self.strategy == "both":
            path = request.url.path
            match = re.match(r'^/(v\d+)(?:/|$)', path)
            if match:
                requested_version = match.group(1)
                # Remove version prefix from path for routing
                request.scope["path"] = path.replace(f"/{requested_version}", "", 1)
        
        # Strategy 2: Custom header
        if not requested_version and (self.strategy == "header" or self.strategy == "both"):
            requested_version = request.headers.get(self.version_header)
        
        # Strategy 3: Accept header (e.g., application/vnd.crownstar.v2+json)
        if not requested_version and self.strategy in ["accept", "both"]:
            accept = request.headers.get("Accept", "")
            match = re.search(self.accept_header_regex, accept)
            if match:
                requested_version = f"v{match.group(1)}"
        
        # Strategy 4: Query parameter (?api-version=v2)
        if not requested_version:
            requested_version = request.query_params.get("api-version") or request.query_params.get("version")
        
        # Validate version
        if requested_version:
            version_info = self.registry.get_version(requested_version)
            if not version_info:
                raise HTTPException(status_code=404, detail=f"API version {requested_version} not found")
            
            # Check sunset
            if self.registry.is_sunset(requested_version):
                raise HTTPException(status_code=410, detail=f"API version {requested_version} has been sunset. Please upgrade.")
            
            # Store version in request state
            request.state.api_version = requested_version
            request.state.version_info = version_info
        else:
            # Use default version
            default_version = self.registry.default_version
            request.state.api_version = default_version
            request.state.version_info = self.registry.get_version(default_version)
        
        # Add version to request headers for downstream handlers
        request.headers.__dict__["_list"].append((b"x-api-version", request.state.api_version.encode()))
        
        response = await call_next(request)
        
        # Add version deprecation/sunset headers to response
        deprecation_headers = self.registry.get_deprecation_headers(request.state.api_version)
        for key, value in deprecation_headers.items():
            response.headers[key] = value
        response.headers["X-API-Version"] = request.state.api_version
        
        return response

# Helper to get version in endpoints
from fastapi import Request
def get_api_version(request: Request) -> str:
    return getattr(request.state, "api_version", "v2")

def get_version_info(request: Request):
    return getattr(request.state, "version_info", None)
