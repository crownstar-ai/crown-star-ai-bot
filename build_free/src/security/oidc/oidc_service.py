# security/oidc/oidc_service.py – OIDC provider integration
import json
import requests
import os
from typing import Dict, Optional, Any
from jose import jwt, jwk
from jose.utils import base64url_decode
import time
from pathlib import Path

class OIDCProvider:
    def __init__(self, provider_name: str, config: Dict):
        self.name = provider_name
        self.issuer = config["issuer"]
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.authorization_endpoint = config.get("authorization_endpoint")
        self.token_endpoint = config.get("token_endpoint")
        self.userinfo_endpoint = config.get("userinfo_endpoint")
        self.jwks_uri = config.get("jwks_uri")
        self._jwks = None
        self._jwks_cache_time = 0
    
    def _get_jwks(self):
        if not self.jwks_uri:
            return None
        # Cache for 1 hour
        if self._jwks and (time.time() - self._jwks_cache_time) < 3600:
            return self._jwks
        resp = requests.get(self.jwks_uri, timeout=10)
        if resp.status_code == 200:
            self._jwks = resp.json()
            self._jwks_cache_time = time.time()
            return self._jwks
        return None
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode JWT, or introspect opaque token"""
        # Try JWT first
        try:
            unverified = jwt.get_unverified_claims(token)
            kid = jwt.get_unverified_header(token).get("kid")
            jwks = self._get_jwks()
            if jwks:
                key = None
                for k in jwks.get("keys", []):
                    if k.get("kid") == kid:
                        key = jwk.construct(k)
                        break
                if key:
                    payload = jwt.decode(token, key, algorithms=["RS256"], audience=self.client_id)
                    # Validate issuer
                    if payload.get("iss") != self.issuer:
                        return None
                    return payload
        except:
            pass
        # Opaque token introspection
        if self.token_endpoint and self.client_id and self.client_secret:
            try:
                resp = requests.post(
                    self.token_endpoint,
                    data={"token": token, "token_type_hint": "access_token"},
                    auth=(self.client_id, self.client_secret),
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("active"):
                        return data
            except:
                pass
        return None
    
    def get_userinfo(self, token: str) -> Optional[Dict]:
        if not self.userinfo_endpoint:
            return None
        try:
            resp = requests.get(
                self.userinfo_endpoint,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return None

class OIDCService:
    def __init__(self, config_path: str = "config/security/oidc/providers.json"):
        self.providers = {}
        self._load_config(config_path)
    
    def _load_config(self, path):
        default = {
            "providers": {
                "auth0": {
                    "issuer": "https://crownstar.auth0.com/",
                    "client_id": "",
                    "client_secret": "",
                    "jwks_uri": "https://crownstar.auth0.com/.well-known/jwks.json"
                },
                "okta": {
                    "issuer": "https://crownstar.okta.com",
                    "client_id": "",
                    "client_secret": ""
                },
                "google": {
                    "issuer": "https://accounts.google.com",
                    "client_id": "",
                    "client_secret": "",
                    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs"
                },
                "microsoft": {
                    "issuer": "https://login.microsoftonline.com/common/v2.0",
                    "client_id": "",
                    "client_secret": "",
                    "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys"
                }
            },
            "default_provider": "auth0"
        }
        if Path(path).exists():
            with open(path, 'r') as f:
                user = json.load(f)
                # Merge
                for k, v in user.get("providers", {}).items():
                    default["providers"][k] = v
                default["default_provider"] = user.get("default_provider", default["default_provider"])
        for name, cfg in default["providers"].items():
            self.providers[name] = OIDCProvider(name, cfg)
    
    def verify_token(self, token: str, provider_hint: str = None) -> Optional[Dict]:
        if provider_hint and provider_hint in self.providers:
            result = self.providers[provider_hint].verify_token(token)
            if result:
                return result
        # Try all providers
        for name, provider in self.providers.items():
            result = provider.verify_token(token)
            if result:
                result["provider"] = name
                return result
        return None
    
    def get_userinfo(self, token: str, provider_hint: str = None) -> Optional[Dict]:
        provider = self.providers.get(provider_hint) if provider_hint else next(iter(self.providers.values()))
        if provider:
            return provider.get_userinfo(token)
        return None

_oidc = None
def get_oidc_service():
    global _oidc
    if _oidc is None:
        _oidc = OIDCService()
    return _oidc
