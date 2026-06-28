# logging/secure_audit.py – Signed audit logs
import json
import hmac
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

class SecureAuditLogger:
    def __init__(self, log_dir: str = "data/logs", secret_key: bytes = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.log_dir / "audit.jsonl"
        if secret_key is None:
            secret_key = b"crownstar-audit-secret-2026"
        self.secret_key = secret_key
    
    def _sign(self, data: str) -> str:
        return hmac.new(self.secret_key, data.encode(), hashlib.sha256).hexdigest()
    
    def log(self, event_type: str, user_id: str, details: Dict, severity: str = "info"):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "severity": severity,
            "details": details
        }
        entry_json = json.dumps(entry)
        signature = self._sign(entry_json)
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(f"{entry_json}||{signature}\n")
        return entry
    
    def verify_logs(self) -> bool:
        """Verify integrity of all logs"""
        if not self.audit_file.exists():
            return True
        with open(self.audit_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.rsplit("||", 1)
                if len(parts) != 2:
                    return False
                data, signature = parts
                if self._sign(data) != signature:
                    return False
        return True

# Global instance
_audit = None
def get_audit():
    global _audit
    if _audit is None:
        _audit = SecureAuditLogger()
    return _audit
