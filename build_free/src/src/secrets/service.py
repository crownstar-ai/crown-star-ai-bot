# secrets/service.py – Core secrets management with caching and fallback
import json
import os
import time
import threading
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from .providers.base import get_provider, SecretMetadata

class SecretsService:
    def __init__(self, config_path: str = "config/secrets/config.json"):
        self.config = self._load_config(config_path)
        self.provider = get_provider(self.config["provider"], self.config.get(self.config["provider"], {}))
        self.cache = {}
        self.cache_ttl = self.config.get("cache_ttl_seconds", 300)
        self._lock = threading.RLock()
        self._start_rotation_scheduler()
    
    def _load_config(self, path):
        default = {
            "provider": "local",
            "hashicorp_vault": {"url": "http://localhost:8200", "token": "", "mount_point": "secret"},
            "aws": {"region": "us-east-1"},
            "azure": {"vault_url": "https://myvault.vault.azure.net"},
            "gcp": {"project_id": ""},
            "cache_ttl_seconds": 300,
            "rotation": {
                "enabled": False,
                "interval_days": 30,
                "keys": []
            }
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _start_rotation_scheduler(self):
        if not self.config["rotation"]["enabled"]:
            return
        def rotate_loop():
            import time as time_module
            while True:
                time_module.sleep(86400)  # daily check
                for key in self.config["rotation"]["keys"]:
                    self._rotate_if_needed(key)
        threading.Thread(target=rotate_loop, daemon=True).start()
    
    def _rotate_if_needed(self, key: str):
        meta = self.provider.get_metadata(key)
        if meta and (datetime.utcnow() - meta.updated_at).days >= self.config["rotation"]["interval_days"]:
            self.provider.rotate(key)
            self.cache.pop(key, None)
    
    def _get_cached(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self.cache.get(key)
            if entry and entry["expires"] > time.time():
                return entry["value"]
            return None
    def _set_cached(self, key: str, value: str):
        with self._lock:
            self.cache[key] = {"value": value, "expires": time.time() + self.cache_ttl}
    def get(self, key: str, version: str = "latest") -> Optional[str]:
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        value = self.provider.get(key, version)
        if value is not None:
            self._set_cached(key, value)
        return value
    def set(self, key: str, value: str, metadata: Dict = None) -> bool:
        success = self.provider.set(key, value, metadata)
        if success:
            self._set_cached(key, value)
        return success
    def delete(self, key: str) -> bool:
        success = self.provider.delete(key)
        if success:
            with self._lock:
                self.cache.pop(key, None)
        return success
    def list_keys(self, prefix: str = "") -> List[str]:
        return self.provider.list_keys(prefix)
    def get_metadata(self, key: str) -> Optional[SecretMetadata]:
        return self.provider.get_metadata(key)
    def rotate(self, key: str, new_value: str = None) -> Optional[str]:
        new_val = self.provider.rotate(key, new_value)
        if new_val:
            self._set_cached(key, new_val)
        return new_val
    def resolve_env(self, value: str) -> str:
        """Expand ${SECRET:path} syntax in string"""
        import re
        def repl(match):
            path = match.group(1)
            val = self.get(path)
            return val if val is not None else match.group(0)
        return re.sub(r'\$\{SECRET:([^}]+)\}', repl, value)
    
    def resolve_config(self, config_dict: Dict) -> Dict:
        """Recursively resolve secrets in a configuration dictionary"""
        result = {}
        for k, v in config_dict.items():
            if isinstance(v, dict):
                result[k] = self.resolve_config(v)
            elif isinstance(v, str):
                result[k] = self.resolve_env(v)
            else:
                result[k] = v
        return result

_secrets = None
def get_secrets():
    global _secrets
    if _secrets is None:
        _secrets = SecretsService()
    return _secrets
