# governance/service.py – Data governance policies and enforcement
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

class GovernanceService:
    def __init__(self, config_path: str = "config/lineage/governance.json"):
        self.config_path = config_path
        self.policies = self._load_policies()
    
    def _load_policies(self) -> Dict:
        default = {
            "retention": {
                "conversation_logs_days": 90,
                "audit_logs_days": 365,
                "lineage_events_days": 30
            },
            "anonymization": {
                "enabled": True,
                "fields": ["user_id", "email", "ip_address", "api_key"],
                "method": "hash"  # hash, mask, drop
            },
            "access_control": {
                "require_approval_for_export": True,
                "audit_all_access": True
            },
            "data_classification": {
                "sensitive_patterns": [
                    "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",  # email
                    "\\b\\d{3}[-.]?\\d{3}[-.]?\\d{4}\\b"  # phone
                ]
            }
        }
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def save_policies(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.policies, f, indent=2)
    
    def anonymize(self, text: str) -> str:
        if not self.policies["anonymization"]["enabled"]:
            return text
        method = self.policies["anonymization"]["method"]
        for pattern in self.policies["data_classification"]["sensitive_patterns"]:
            if method == "hash":
                import hashlib
                def repl(match):
                    return hashlib.md5(match.group(0).encode()).hexdigest()[:8]
                text = re.sub(pattern, repl, text)
            elif method == "mask":
                text = re.sub(pattern, "[REDACTED]", text)
        return text
    
    def check_retention(self, file_path: str) -> bool:
        """Check if file is within retention period"""
        if not os.path.exists(file_path):
            return False
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
        days_old = (datetime.now() - mtime).days
        for category, days in self.policies["retention"].items():
            if category in file_path:
                return days_old <= days
        return True
    
    def apply_retention_policy(self, directory: str = "data"):
        """Delete files older than retention period"""
        deleted = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                path = os.path.join(root, f)
                if not self.check_retention(path):
                    os.remove(path)
                    deleted.append(path)
        return deleted
    
    def get_policy_summary(self) -> Dict:
        return self.policies

_governance = None
def get_governance():
    global _governance
    if _governance is None:
        _governance = GovernanceService()
    return _governance
