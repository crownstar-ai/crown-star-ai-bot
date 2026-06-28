# baas/service.py – Backup as a Service orchestrator
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from .providers.base import get_provider, BackupMetadata, RestoreOptions

class BaaSService:
    def __init__(self, config_path: str = "config/baas/config.json"):
        self.config = self._load_config(config_path)
        self.provider = get_provider(self.config["provider"], self.config.get(self.config["provider"], {}))
        self.backup_policies = self.config.get("policies", [])
        self._schedule_thread = None
        self._running = False
        self._start_scheduler()
    
    def _load_config(self, path):
        default = {
            "provider": "local",
            "aws": {"region": "us-east-1", "role_arn": ""},
            "azure": {"subscription_id": "", "resource_group": "", "vault_name": ""},
            "gcp": {"project_id": "", "location": "us-central1"},
            "veeam": {},
            "commvault": {},
            "policies": [
                {"name": "daily", "schedule": "0 2 * * *", "source": "data", "retention_days": 30},
                {"name": "weekly", "schedule": "0 3 * * 0", "source": "data", "retention_days": 90},
                {"name": "monthly", "schedule": "0 4 1 * *", "source": "config", "retention_days": 365}
            ]
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _start_scheduler(self):
        self._running = True
        self._schedule_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._schedule_thread.start()
    
    def _scheduler_loop(self):
        from croniter import croniter
        import time as time_module
        # Keep track of next run times
        next_runs = {}
        for policy in self.backup_policies:
            iter = croniter(policy["schedule"], time_module.time())
            next_runs[policy["name"]] = iter.get_next()
        while self._running:
            now = time_module.time()
            for policy in self.backup_policies:
                if now >= next_runs[policy["name"]]:
                    # Trigger backup
                    self.create_backup(policy["source"], policy["name"], policy["retention_days"])
                    # Schedule next
                    iter = croniter(policy["schedule"], time_module.time())
                    next_runs[policy["name"]] = iter.get_next()
            time_module.sleep(60)
    
    def create_backup(self, source_path: str, description: str = "", retention_days: int = 30) -> Optional[BackupMetadata]:
        return self.provider.create_backup(source_path, description, retention_days)
    
    def list_backups(self, source: str = None) -> List[BackupMetadata]:
        return self.provider.list_backups(source)
    
    def restore_backup(self, backup_id: str, target_path: str = None, point_in_time: datetime = None, overwrite: bool = False) -> bool:
        options = RestoreOptions(target_path=target_path, point_in_time=point_in_time, overwrite=overwrite)
        return self.provider.restore_backup(backup_id, options)
    
    def delete_backup(self, backup_id: str) -> bool:
        return self.provider.delete_backup(backup_id)
    
    def get_backup_details(self, backup_id: str) -> Optional[BackupMetadata]:
        return self.provider.get_backup_details(backup_id)
    
    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity by restoring to isolated temporary location"""
        return self.provider.verify_backup(backup_id)
    
    def get_status(self) -> Dict:
        return {
            "provider": self.config["provider"],
            "policies": self.backup_policies,
            "backups": [{"id": b.backup_id, "source": b.source, "created": b.created_at.isoformat(), "size_mb": round(b.size_bytes/1024/1024,2)} for b in self.list_backups()[:20]]
        }

_baas_service = None
def get_baas_service():
    global _baas_service
    if _baas_service is None:
        _baas_service = BaaSService()
    return _baas_service
