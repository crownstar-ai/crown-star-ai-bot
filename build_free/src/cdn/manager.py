# cdn/manager.py – CrownStar Global CDN & Edge Caching Engine
import os, json, time, hashlib, requests, threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class CDNProvider(Enum):
    CLOUDFRONT = "aws_cloudfront"
    CLOUDFLARE = "cloudflare"
    FASTLY = "fastly"
    AZURE_CDN = "azure_cdn"
    SOVEREIGN_AU = "sovereign_au"   # Australian sovereign CDN node

@dataclass
class CDNConfiguration:
    provider: CDNProvider
    distribution_id: Optional[str]
    zone_id: Optional[str]          # Cloudflare
    service_id: Optional[str]       # Fastly
    endpoint: str
    api_key: Optional[str]
    api_token: Optional[str]
    enabled: bool = True

@dataclass
class CacheRule:
    path_pattern: str           # regex or prefix
    ttl_seconds: int
    edge_ttl_seconds: Optional[int]
    cache_key_headers: List[str]
    cache_key_cookies: List[str]
    bypass_on_cookie: Optional[str]
    geo_restrictions: List[str]   # allowed country codes

@dataclass
class PurgeResult:
    success: bool
    provider: str
    paths: List[str]
    message: str
    timestamp: int

class CDNManager:
    """Unified interface for multiple CDN providers, including Australian sovereign nodes."""
    def __init__(self, config_path="config/cdn/providers.json"):
        self.providers: Dict[str, CDNConfiguration] = {}
        self.rules: List[CacheRule] = []
        self._load_config(config_path)
        self._init_clients()

    def _load_config(self, path):
        default = {
            "default_provider": "cloudflare",
            "providers": {
                "cloudflare": {
                    "enabled": True,
                    "zone_id": os.environ.get("CF_ZONE_ID", ""),
                    "api_token": os.environ.get("CF_API_TOKEN", ""),
                    "endpoint": "https://api.cloudflare.com/client/v4"
                },
                "aws_cloudfront": {
                    "enabled": False,
                    "distribution_id": "",
                    "access_key": "",
                    "secret_key": "",
                    "region": "us-east-1"
                },
                "fastly": {
                    "enabled": False,
                    "service_id": "",
                    "api_token": ""
                },
                "sovereign_au": {
                    "enabled": True,
                    "endpoint": "https://cdn.sovereign.cloud.gov.au/v1",
                    "api_key": os.environ.get("SOVEREIGN_CDN_KEY", "")
                }
            },
            "default_rules": [
                {"path_pattern": "/models/*", "ttl_seconds": 86400, "edge_ttl": 3600},
                {"path_pattern": "/index/*", "ttl_seconds": 604800, "edge_ttl": 86400},
                {"path_pattern": "/static/*", "ttl_seconds": 31536000, "edge_ttl": 86400},
                {"path_pattern": "/api/*", "ttl_seconds": 0, "edge_ttl": 0}  # no cache
            ]
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        # Build provider configs
        for name, cfg in default.get("providers", {}).items():
            if cfg.get("enabled"):
                prov = CDNProvider(name) if name in [p.value for p in CDNProvider] else CDNProvider.SOVEREIGN_AU
                self.providers[name] = CDNConfiguration(
                    provider=prov,
                    distribution_id=cfg.get("distribution_id"),
                    zone_id=cfg.get("zone_id"),
                    service_id=cfg.get("service_id"),
                    endpoint=cfg.get("endpoint", ""),
                    api_key=cfg.get("api_key"),
                    api_token=cfg.get("api_token"),
                    enabled=cfg.get("enabled", True)
                )
        for rule in default.get("default_rules", []):
            self.rules.append(CacheRule(
                path_pattern=rule["path_pattern"],
                ttl_seconds=rule["ttl_seconds"],
                edge_ttl_seconds=rule.get("edge_ttl"),
                cache_key_headers=rule.get("cache_key_headers", []),
                cache_key_cookies=rule.get("cache_key_cookies", []),
                bypass_on_cookie=rule.get("bypass_on_cookie"),
                geo_restrictions=rule.get("geo_restrictions", [])
            ))

    def _init_clients(self):
        self.clients = {}
        for name, cfg in self.providers.items():
            if cfg.provider == CDNProvider.CLOUDFLARE:
                self.clients[name] = CloudflareClient(cfg)
            elif cfg.provider == CDNProvider.CLOUDFRONT:
                self.clients[name] = CloudFrontClient(cfg)
            elif cfg.provider == CDNProvider.FASTLY:
                self.clients[name] = FastlyClient(cfg)
            elif cfg.provider == CDNProvider.SOVEREIGN_AU:
                self.clients[name] = SovereignCDNClient(cfg)

    def purge_paths(self, paths: List[str], provider: Optional[str] = None, all_providers: bool = False) -> List[PurgeResult]:
        """Purge cached paths from CDN(s)."""
        results = []
        targets = self._get_target_providers(provider, all_providers)
        for name, client in targets.items():
            try:
                purge_resp = client.purge(paths)
                results.append(PurgeResult(
                    success=purge_resp.get("success", False),
                    provider=name,
                    paths=paths,
                    message=purge_resp.get("message", ""),
                    timestamp=int(time.time())
                ))
            except Exception as e:
                results.append(PurgeResult(False, name, paths, str(e), int(time.time())))
        return results

    def invalidate_path(self, path: str, provider: Optional[str] = None) -> Dict:
        """Invalidate a single path (alias for purge with single path)."""
        res = self.purge_paths([path], provider)
        return asdict(res[0]) if res else {"error": "no provider"}

    def prefetch_assets(self, asset_urls: List[str], provider: Optional[str] = None) -> Dict:
        """Warm up CDN cache by requesting assets in background."""
        targets = self._get_target_providers(provider, False)
        results = {}
        for name, client in targets.items():
            warmed = []
            for url in asset_urls:
                try:
                    # Make a HEAD request to populate edge cache (if supported)
                    resp = client.warm_url(url)
                    warmed.append({"url": url, "status": resp.get("status", 200)})
                except Exception as e:
                    warmed.append({"url": url, "error": str(e)})
            results[name] = warmed
        return results

    def get_cdn_status(self, provider: Optional[str] = None) -> Dict:
        """Retrieve CDN health and statistics."""
        targets = self._get_target_providers(provider, True)
        status = {}
        for name, client in targets.items():
            status[name] = client.get_status()
        return status

    def apply_geo_restrictions(self, country_codes: List[str], provider: Optional[str] = None) -> Dict:
        """Update geo‑blocking rules on CDN."""
        targets = self._get_target_providers(provider, False)
        results = {}
        for name, client in targets.items():
            results[name] = client.update_geo_rules(country_codes)
        return results

    def _get_target_providers(self, specific: Optional[str], all_flag: bool) -> Dict:
        if specific:
            return {specific: self.clients[specific]} if specific in self.clients else {}
        if all_flag:
            return self.clients
        # default: use first enabled provider
        default = next(iter(self.clients.values())) if self.clients else None
        return {default: self.clients[default]} if default else {}

# --------------------------------------------------------------------
# Provider‑specific clients (stubs with real API integration commented)
# --------------------------------------------------------------------
class CloudflareClient:
    def __init__(self, cfg):
        self.zone_id = cfg.zone_id
        self.api_token = cfg.api_token
        self.endpoint = cfg.endpoint
    def purge(self, paths):
        # POST /zones/{zone_id}/purge_cache
        return {"success": True, "message": f"Purged {len(paths)} paths on Cloudflare"}
    def warm_url(self, url):
        return {"status": 200}
    def get_status(self):
        return {"provider": "cloudflare", "zone": self.zone_id, "healthy": True}
    def update_geo_rules(self, codes):
        return {"success": True, "geo_restrictions": codes}

class CloudFrontClient:
    def __init__(self, cfg):
        self.dist_id = cfg.distribution_id
    def purge(self, paths):
        # Use boto3 create_invalidation
        return {"success": True, "message": f"Invalidation created for {len(paths)} paths"}
    def warm_url(self, url):
        return {"status": 200}
    def get_status(self):
        return {"provider": "cloudfront", "distribution": self.dist_id}
    def update_geo_rules(self, codes):
        # Geo restriction via AWS WAF
        return {"success": True}

class FastlyClient:
    def __init__(self, cfg):
        self.service_id = cfg.service_id
        self.api_token = cfg.api_token
    def purge(self, paths):
        return {"success": True, "message": "Purged"}
    def warm_url(self, url):
        return {"status": 202}
    def get_status(self):
        return {"provider": "fastly", "service": self.service_id}
    def update_geo_rules(self, codes):
        return {"success": True}

class SovereignCDNClient:
    def __init__(self, cfg):
        self.endpoint = cfg.endpoint
        self.api_key = cfg.api_key
    def purge(self, paths):
        # Call Australian sovereign CDN API
        return {"success": True, "message": f"Purged {len(paths)} assets from AU sovereign nodes"}
    def warm_url(self, url):
        # Prefetch to edge
        return {"status": 200}
    def get_status(self):
        return {"provider": "sovereign_au", "endpoint": self.endpoint, "healthy": True}
    def update_geo_rules(self, codes):
        # AU CDN may restrict traffic to AU/NZ
        return {"success": True, "geo_restrictions": codes}

_cdn_manager = None
def get_cdn_manager():
    global _cdn_manager
    if _cdn_manager is None:
        _cdn_manager = CDNManager()
    return _cdn_manager
