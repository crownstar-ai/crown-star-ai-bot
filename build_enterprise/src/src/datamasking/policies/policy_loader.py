# datamasking/policies/policy_loader.py – Load masking policies from JSON
import json
from pathlib import Path
from typing import Dict, Optional

class PolicyLoader:
    def __init__(self, config_path: str = "config/masking/policies.json"):
        self.config_path = config_path
        self.policies = self._load()
    
    def _load(self):
        default = {
            "email": {
                "default": {"mask_type": "partial", "viewer_roles": ["admin", "auditor"]},
                "export": {"mask_type": "hash"}
            },
            "phone": {
                "default": {"mask_type": "partial", "viewer_roles": ["admin"]},
                "export": {"mask_type": "full"}
            },
            "ssn": {
                "default": {"mask_type": "full", "viewer_roles": ["admin"]},
                "export": {"mask_type": "redact"}
            },
            "credit_card": {
                "default": {"mask_type": "partial", "viewer_roles": ["admin", "finance"]},
                "export": {"mask_type": "token"}
            },
            "name": {
                "default": {"mask_type": "partial", "viewer_roles": ["admin", "user"]},
                "export": {"mask_type": "full"}
            },
            "address": {
                "default": {"mask_type": "partial", "viewer_roles": ["admin"]},
                "export": {"mask_type": "hash"}
            },
            "ipv4": {
                "default": {"mask_type": "partial", "viewer_roles": ["admin", "devops"]},
                "export": {"mask_type": "full"}
            }
        }
        if Path(self.config_path).exists():
            with open(self.config_path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def get_policy(self, field_type: str, policy_name: str = "default") -> Optional[Dict]:
        return self.policies.get(field_type, {}).get(policy_name)
    
    def reload(self):
        self.policies = self._load()

_policy_loader = None
def get_policy_loader():
    global _policy_loader
    if _policy_loader is None:
        _policy_loader = PolicyLoader()
    return _policy_loader
