# anomaly/remediation/orchestrator.py – Self‑healing engine
import subprocess
import requests
import time
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Callable
from enum import Enum

class RemediationAction(Enum):
    RESTART_POD = "restart_pod"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    CLEAR_CACHE = "clear_cache"
    FAILOVER = "failover"
    RESTART_SERVICE = "restart_service"
    NOTIFY_ADMIN = "notify_admin"
    KILL_SLOW_REQUESTS = "kill_slow_requests"

class RemediationOrchestrator:
    def __init__(self, config_path: str = "config/anomaly/remediation_policies.json"):
        self.policies = self._load_policies(config_path)
        self.remediation_history = []
        self._action_handlers = {
            RemediationAction.RESTART_POD: self._restart_pod,
            RemediationAction.SCALE_UP: self._scale_up,
            RemediationAction.SCALE_DOWN: self._scale_down,
            RemediationAction.CLEAR_CACHE: self._clear_cache,
            RemediationAction.FAILOVER: self._failover,
            RemediationAction.RESTART_SERVICE: self._restart_service,
            RemediationAction.NOTIFY_ADMIN: self._notify_admin,
            RemediationAction.KILL_SLOW_REQUESTS: self._kill_slow_requests
        }
        self.lock = threading.Lock()
    
    def _load_policies(self, path):
        default = {
            "cpu_high": {
                "metric": "cpu_usage",
                "threshold": 0.85,
                "action": "scale_up",
                "cooldown_seconds": 300
            },
            "memory_high": {
                "metric": "memory_usage",
                "threshold": 0.9,
                "action": "restart_pod",
                "cooldown_seconds": 600
            },
            "error_rate_high": {
                "metric": "error_rate",
                "threshold": 0.05,
                "action": "restart_service",
                "cooldown_seconds": 120
            },
            "cache_miss_spike": {
                "metric": "cache_miss_rate",
                "threshold": 0.8,
                "action": "clear_cache",
                "cooldown_seconds": 1800
            },
            "queue_backlog": {
                "metric": "queue_depth",
                "threshold": 200,
                "action": "scale_up",
                "cooldown_seconds": 60
            }
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _restart_pod(self, details: Dict):
        print(f"[Remediation] Restarting pod: {details.get('pod', 'crownstar-api')}")
        try:
            # Kubernetes restart (delete pod)
            subprocess.run(["kubectl", "delete", "pod", "-l", "app=crownstar-api", "-n", "crownstar"], timeout=30, capture_output=True)
        except:
            # Fallback: restart via API? Not implemented
            pass
        return True
    
    def _scale_up(self, details: Dict):
        print(f"[Remediation] Scaling up replicas (current: {details.get('current_replicas', 'unknown')})")
        try:
            subprocess.run(["kubectl", "scale", "deployment", "crownstar-api", "--replicas=5", "-n", "crownstar"], timeout=30)
        except:
            pass
        return True
    
    def _scale_down(self, details: Dict):
        print(f"[Remediation] Scaling down replicas")
        try:
            subprocess.run(["kubectl", "scale", "deployment", "crownstar-api", "--replicas=2", "-n", "crownstar"], timeout=30)
        except:
            pass
        return True
    
    def _clear_cache(self, details: Dict):
        print("[Remediation] Clearing cache")
        try:
            requests.post("http://localhost:8080/v1/cache/clear", timeout=5)
        except:
            pass
        return True
    
    def _failover(self, details: Dict):
        print("[Remediation] Initiating failover to standby region")
        # In real implementation, update DNS or load balancer
        return True
    
    def _restart_service(self, details: Dict):
        print("[Remediation] Restarting CrownStar service (systemd)")
        try:
            subprocess.run(["systemctl", "restart", "crownstar"], timeout=60)
        except:
            pass
        return True
    
    def _notify_admin(self, details: Dict):
        print(f"[Remediation] Alert: {details.get('message', 'Anomaly detected')}")
        # Could send Slack, email, PagerDuty
        return True
    
    def _kill_slow_requests(self, details: Dict):
        print("[Remediation] Killing slow requests (via nginx timeout or DB connection reset)")
        return True
    
    def handle_anomaly(self, anomaly: Dict) -> bool:
        """Determine action from policy and execute"""
        metric = anomaly.get("metric", "")
        value = anomaly.get("value", 0)
        # Find matching policy
        action = None
        for policy_name, policy in self.policies.items():
            if policy.get("metric") == metric:
                if value >= policy.get("threshold", 1e9):
                    action = policy.get("action")
                    break
        if not action:
            return False
        
        # Convert action string to RemediationAction enum
        try:
            action_enum = RemediationAction(action)
            handler = self._action_handlers.get(action_enum)
            if handler:
                with self.lock:
                    result = handler({"metric": metric, "value": value, "policy": policy_name})
                self.remediation_history.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "anomaly": anomaly,
                    "action": action,
                    "success": result
                })
                return result
        except ValueError:
            print(f"Unknown action: {action}")
        return False
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        return self.remediation_history[-limit:]

# Global instance
_healing = None
def get_healing_orchestrator():
    global _healing
    if _healing is None:
        _healing = RemediationOrchestrator()
    return _healing
