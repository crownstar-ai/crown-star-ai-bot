# ====================================================================================================
# api_auth.py – API key authentication for CrownStar‑Absolute Enterprise REST API
# Features:
#   - JWT (JSON Web Token) creation and validation (HS256, RS256)
#   - API key management (generate, validate, rotate)
#   - Rate limiting per API key (optional)
#   - Scope / permission checking
#   - Integration with FastAPI/Flask via dependency injection
#   - Support for Bearer tokens and X-API-Key headers
# ====================================================================================================

import os
import time
import secrets
import hashlib
import hmac
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

# Try to import JWT libraries
try:
    import jwt
    from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, InvalidSignatureError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logger.warning("PyJWT not installed. Install with: pip install PyJWT")

# Try to import cryptography for RSA
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography not installed. RSA support disabled.")

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
@dataclass
class AuthConfig:
    """Authentication configuration for enterprise API."""
    jwt_secret: str = field(default_factory=lambda: os.environ.get("CROWNSTAR_JWT_SECRET", "change-this-secret"))
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    refresh_expiry_days: int = 7
    api_key_header: str = "X-API-Key"
    enable_api_keys: bool = True
    enable_jwt: bool = True
    allow_bearer_token: bool = True

# --------------------------------------------------------------------
# API Key Management (for service accounts)
# --------------------------------------------------------------------
class APIKeyManager:
    """
    Manage static API keys (pre‑shared keys for service accounts).
    Keys are stored encrypted (see encryption.py) or in environment variables.
    """
    
    def __init__(self, storage_file: Optional[str] = None):
        self.storage_file = storage_file
        self._keys: Dict[str, Dict] = {}
        if storage_file:
            self._load_keys()
        else:
            # Use environment variables for simplicity in production
            self._load_from_env()
    
    def _load_from_env(self):
        """Load API keys from environment variables (CROWNSTAR_API_KEY_<name>=<key>)."""
        for key, value in os.environ.items():
            if key.startswith("CROWNSTAR_API_KEY_"):
                name = key.replace("CROWNSTAR_API_KEY_", "").lower()
                self._keys[name] = {
                    "key": value,
                    "scopes": ["api:all"],
                    "tier": "enterprise",
                    "created": time.time()
                }
    
    def _load_keys(self):
        """Load keys from JSON file (encrypted recommended)."""
        try:
            with open(self.storage_file, 'r') as f:
                self._keys = json.load(f)
        except FileNotFoundError:
            logger.warning(f"API key file {self.storage_file} not found")
    
    def save_keys(self):
        """Save keys to JSON file (call encryption wrapper in production)."""
        if self.storage_file:
            with open(self.storage_file, 'w') as f:
                json.dump(self._keys, f, indent=2)
    
    def generate_key(self, name: str, scopes: List[str] = None, tier: str = "enterprise") -> str:
        """Generate a new API key (32 bytes hex)."""
        key = secrets.token_hex(32)
        self._keys[name] = {
            "key": key,
            "scopes": scopes or ["api:all"],
            "tier": tier,
            "created": time.time(),
            "last_used": None
        }
        self.save_keys()
        logger.info(f"API key generated for {name}")
        return key
    
    def validate_key(self, api_key: str) -> Optional[Dict]:
        """Validate an API key and return its metadata."""
        for name, data in self._keys.items():
            if data["key"] == api_key:
                # Update last used timestamp
                data["last_used"] = time.time()
                self.save_keys()
                return {
                    "name": name,
                    "scopes": data["scopes"],
                    "tier": data["tier"],
                    "authenticated": True
                }
        return None
    
    def revoke_key(self, name: str) -> bool:
        """Revoke an API key by name."""
        if name in self._keys:
            del self._keys[name]
            self.save_keys()
            logger.info(f"API key revoked: {name}")
            return True
        return False
    
    def list_keys(self) -> List[Dict]:
        """List all API keys (without exposing the key itself)."""
        return [{"name": k, "scopes": v["scopes"], "tier": v["tier"], "created": v["created"]}
                for k, v in self._keys.items()]

# --------------------------------------------------------------------
# JWT Token Manager
# --------------------------------------------------------------------
class JWTManager:
    """
    Create, validate, and refresh JWT tokens for user authentication.
    Supports HS256 (symmetric) and RS256 (asymmetric) algorithms.
    """
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self._private_key = None
        self._public_key = None
        if config.jwt_algorithm == "RS256" and CRYPTO_AVAILABLE:
            self._load_or_generate_rsa_keys()
    
    def _load_or_generate_rsa_keys(self):
        """Load RSA keys from files or generate new ones."""
        priv_path = "keys/private.pem"
        pub_path = "keys/public.pem"
        import os
        from pathlib import Path
        Path("keys").mkdir(exist_ok=True)
        
        if os.path.exists(priv_path) and os.path.exists(pub_path):
            with open(priv_path, 'rb') as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            with open(pub_path, 'rb') as f:
                self._public_key = serialization.load_pem_public_key(
                    f.read(), backend=default_backend()
                )
        else:
            # Generate new RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            public_key = private_key.public_key()
            
            with open(priv_path, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            with open(pub_path, 'wb') as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            self._private_key = private_key
            self._public_key = public_key
    
    def create_token(self, user_id: str, claims: Dict = None, expiry_minutes: int = None) -> str:
        """
        Create a JWT token for a user.
        
        Args:
            user_id: User identifier
            claims: Additional claims (e.g., roles, scopes)
            expiry_minutes: Override default expiry
        
        Returns:
            Encoded JWT string
        """
        if not JWT_AVAILABLE:
            raise ImportError("PyJWT required for JWT tokens")
        
        expiry = expiry_minutes or self.config.jwt_expiry_minutes
        payload = {
            "sub": user_id,
            "iat": int(time.time()),
            "exp": int(time.time() + expiry * 60),
            "iss": "crownstar-api",
            "aud": "crownstar-client"
        }
        if claims:
            payload.update(claims)
        
        if self.config.jwt_algorithm == "RS256":
            return jwt.encode(payload, self._private_key, algorithm="RS256")
        else:
            return jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create a longer‑lived refresh token."""
        expiry = self.config.refresh_expiry_days * 86400
        payload = {
            "sub": user_id,
            "iat": int(time.time()),
            "exp": int(time.time() + expiry),
            "type": "refresh"
        }
        if self.config.jwt_algorithm == "RS256":
            return jwt.encode(payload, self._private_key, algorithm="RS256")
        else:
            return jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
    
    def validate_token(self, token: str, verify_expiry: bool = True) -> Optional[Dict]:
        """
        Validate a JWT token and return its payload.
        
        Returns:
            Payload dict if valid, None otherwise
        """
        if not JWT_AVAILABLE:
            return None
        
        try:
            if self.config.jwt_algorithm == "RS256":
                payload = jwt.decode(
                    token, self._public_key,
                    algorithms=["RS256"],
                    audience="crownstar-client",
                    issuer="crownstar-api",
                    options={"verify_exp": verify_expiry}
                )
            else:
                payload = jwt.decode(
                    token, self.config.jwt_secret,
                    algorithms=[self.config.jwt_algorithm],
                    audience="crownstar-client",
                    issuer="crownstar-api",
                    options={"verify_exp": verify_expiry}
                )
            return payload
        except ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except InvalidSignatureError:
            logger.debug("Invalid signature")
            return None
        except InvalidTokenError as e:
            logger.debug(f"Invalid token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Validate refresh token and issue a new access token."""
        payload = self.validate_token(refresh_token, verify_expiry=True)
        if not payload or payload.get("type") != "refresh":
            return None
        return self.create_token(payload["sub"])

# --------------------------------------------------------------------
# Authentication Middleware / Dependency (for FastAPI)
# --------------------------------------------------------------------
class AuthMiddleware:
    """
    Authentication handler for FastAPI / Flask.
    Supports:
        - X-API-Key header (static API keys)
        - Authorization: Bearer <JWT>
    """
    
    def __init__(self, config: AuthConfig, api_key_manager: Optional[APIKeyManager] = None):
        self.config = config
        self.api_key_manager = api_key_manager or APIKeyManager()
        self.jwt_manager = JWTManager(config)
    
    def authenticate(self, api_key: str = None, bearer_token: str = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Authenticate a request.
        
        Returns:
            Tuple of (auth_info, error_message). auth_info contains 'user_id', 'scopes', 'tier', etc.
        """
        # Try API key first
        if self.config.enable_api_keys and api_key:
            key_info = self.api_key_manager.validate_key(api_key)
            if key_info:
                return {
                    "type": "api_key",
                    "user_id": key_info["name"],
                    "scopes": key_info["scopes"],
                    "tier": key_info["tier"]
                }, None
        
        # Try Bearer token (JWT)
        if self.config.enable_jwt and bearer_token:
            payload = self.jwt_manager.validate_token(bearer_token)
            if payload:
                return {
                    "type": "jwt",
                    "user_id": payload["sub"],
                    "scopes": payload.get("scopes", ["api:all"]),
                    "tier": payload.get("tier", "enterprise"),
                    "exp": payload.get("exp")
                }, None
        
        return None, "Authentication required: missing or invalid credentials"
    
    def require_scope(self, auth_info: Dict, required_scope: str) -> bool:
        """Check if authenticated user has a required scope."""
        if not auth_info:
            return False
        scopes = auth_info.get("scopes", [])
        return required_scope in scopes or "api:all" in scopes
    
    def require_tier(self, auth_info: Dict, minimum_tier: str) -> bool:
        """Check if authenticated user meets minimum tier requirement."""
        if not auth_info:
            return False
        tier_order = ["free", "basic", "pro", "enterprise"]
        user_tier = auth_info.get("tier", "free")
        if user_tier not in tier_order:
            user_tier = "free"
        if minimum_tier not in tier_order:
            minimum_tier = "free"
        return tier_order.index(user_tier) >= tier_order.index(minimum_tier)

# --------------------------------------------------------------------
# FastAPI Dependency (example)
# --------------------------------------------------------------------
def get_auth_middleware() -> AuthMiddleware:
    """Singleton instance for FastAPI dependency injection."""
    global _auth_middleware
    if not hasattr(get_auth_middleware, "_instance"):
        config = AuthConfig()
        config.jwt_secret = os.environ.get("CROWNSTAR_JWT_SECRET", "change-this-secret")
        get_auth_middleware._instance = AuthMiddleware(config)
    return get_auth_middleware._instance

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Generate API key
key_manager = APIKeyManager()
api_key = key_manager.generate_key("my_service", scopes=["chat:write", "chat:read"])
print(f"API Key: {api_key}")

# Create JWT
jwt_mgr = JWTManager(AuthConfig())
token = jwt_mgr.create_token("user123", claims={"scopes": ["api:all"], "tier": "pro"})
print(f"JWT: {token}")

# Authenticate request
auth = AuthMiddleware(AuthConfig())
auth_info, err = auth.authenticate(api_key=api_key)
if auth_info:
    print(f"Authenticated as {auth_info['user_id']}")
    
# Check scope
if auth.require_scope(auth_info, "chat:write"):
    print("Has write access")
"""

# ====================================================================================================
# END OF api_auth.py
# ====================================================================================================
