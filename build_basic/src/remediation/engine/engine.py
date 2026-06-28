# remediation/engine/engine.py – Auto‑remediation decision engine
import time
import threading
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import deque
from ..actions.actions import RemediationActions

logger = logging.getLogger("crownstar.remediation.engine")

class RemediationEngine:
    def __init__(self, config_path: str = "config/remediation/policies.json"):
        self.config = self._load_config(config_path)
        self.actions = RemediationActions()
        self.remediation_history = []
        self.cooldown_tracker = {}  # policy_id -> last_run_time
        self._event_queue = deque()
        self._running = False
        self._worker = None
    
    def _load_config(self, path):
        default = {
            "policies": [
                {
                    "id": "pod_high_cpu",
                    "condition": "metric: cpu_usage > 0.85",
                    "action": "restart_pod",
                    "cooldown_seconds": 300,
                    "severity": "high",
                    "enabled": True
                },
                {
                    "id": "scale_up_queue_backlog",
                    "condition": "metric: queue_depth > 200",
                    "action": "scale_deployment",
                    "params": {"replicas": 5},
                    "cooldown_seconds": 60,
                    "severity": "medium",
                    "enabled": True
                },
                {
                    "id": "cache_clear_on_high_latency",
                    "condition": "metric: latency_p99 > 2.0",
                    "action": "clear_cache",
                    "cooldown_seconds": 1800,
                    "severity": "low",
                    "enabled": True
                },
                {
                    "id": "failover_region_on_outage",
                    "condition": "alert: region_unhealthy",
                    "action": "failover_region",
                    "cooldown_seconds": 3600,
                    "severity": "critical",
                    "enabled": True
                },
                {
                    "id": "rollback_on_error_spike",
                    "condition": "metric: error_rate > 0.1",
                    "action": "rollback_deployment",
                    "cooldown_seconds": 600,
                    "severity": "high",
                    "enabled": True
                }
            ],
            "metrics_source": "prometheus",
            "prometheus_url": "http://localhost:9090",
            "alert_source": "webhook",
            "webhook_port": 8090,
            "global_cooldown_seconds": 60,
            "max_concurrent_remediations": 2
        }
        import os
        from pathlib import Path
        if Path(path).exists():
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """Evaluate condition string against current context/metrics"""
        # Simple parser: supports "metric: cpu_usage > 0.85", "alert: region_unhealthy", "event: pod_restart"
        parts = condition.split(":", 1)
        if len(parts) != 2:
            return False
        cond_type, expr = parts[0].strip(), parts[1].strip()
        if cond_type == "metric":
            # Extract metric name and threshold
            import re
            match = re.match(r'(\w+)\s*([<>]=?)\s*([0-9.]+)', expr)
            if match:
                metric_name, op, threshold = match.groups()
                threshold = float(threshold)
                current_value = context.get("metrics", {}).get(metric_name, 0)
                if op == ">":
                    return current_value > threshold
                elif op == ">=":
                    return current_value >= threshold
                elif op == "<":
                    return current_value < threshold
                elif op == "<=":
                    return current_value <= threshold
        elif cond_type == "alert":
            # Check if alert is active
            alert_name = expr
            return context.get("alerts", {}).get(alert_name, False)
        elif cond_type == "event":
            # Check if event occurred
            event_type = expr
            return context.get("events", {}).get(event_type, False)
        return False
    
    def _get_metric_value(self, metric_name: str) -> float:
        """Fetch metric from Prometheus (stub – would query actual Prometheus)"""
        # For simulation, return random value
        import random
        # Simulate realistic values based on metric name
        if metric_name == "cpu_usage":
            return random.uniform(0.2, 0.9)
        elif metric_name == "queue_depth":
            return random.randint(0, 300)
        elif metric_name == "latency_p99":
            return random.uniform(0.5, 3.0)
        elif metric_name == "error_rate":
            return random.uniform(0.0, 0.15)
        return 0.0
    
    def _get_current_context(self) -> Dict:
        """Collect current metrics, alerts, events"""
        context = {"metrics": {}, "alerts": {}, "events": {}}
        # Fetch metrics from Prometheus (simplified)
        for policy in self.config["policies"]:
            if not policy["enabled"]:
                continue
            condition = policy["condition"]
            if condition.startswith("metric:"):
                metric_name = condition.split(":")[1].strip().split()[0]
                context["metrics"][metric_name] = self._get_metric_value(metric_name)
        return context
    
    def _is_in_cooldown(self, policy_id: str) -> bool:
        if policy_id not in self.cooldown_tracker:
            return False
        last_run = self.cooldown_tracker[policy_id]
        cooldown = self.config.get("global_cooldown_seconds", 60)
        # Also check policy‑specific cooldown
        for p in self.config["policies"]:
            if p["id"] == policy_id:
                cooldown = p.get("cooldown_seconds", cooldown)
                break
        return (time.time() - last_run) < cooldown
    
    def _record_remediation(self, policy_id: str, action: str, success: bool, details: str = ""):
        self.remediation_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "policy_id": policy_id,
            "action": action,
            "success": success,
            "details": details
        })
        # Trim history
        if len(self.remediation_history) > 1000:
            self.remediation_history = self.remediation_history[-500:]
    
    def evaluate_and_remediate(self) -> List[Dict]:
        """Run through all policies, trigger actions when conditions met"""
        results = []
        context = self._get_current_context()
        active_actions = 0
        for policy in self.config["policies"]:
            if not policy["enabled"]:
                continue
            if self._is_in_cooldown(policy["id"]):
                continue
            if self._evaluate_condition(policy["condition"], context):
                action_name = policy["action"]
                params = policy.get("params", {})
                # Run action
                action_method = getattr(self.actions, action_name, None)
                if not action_method:
                    logger.error(f"Unknown action: {action_name}")
                    continue
                try:
                    success = action_method(**params)
                    self._record_remediation(policy["id"], action_name, success, str(params))
                    self.cooldown_tracker[policy["id"]] = time.time()
                    results.append({
                        "policy": policy["id"],
                        "action": action_name,
                        "success": success,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    active_actions += 1
                    if active_actions >= self.config.get("max_concurrent_remediations", 2):
                        break
                except Exception as e:
                    logger.error(f"Action {action_name} failed: {e}")
                    self._record_remediation(policy["id"], action_name, False, str(e))
        return results
    
    def start_periodic(self, interval_seconds: int = 30):
        """Run remediation check periodically in background"""
        self._running = True
        def loop():
            while self._running:
                try:
                    self.evaluate_and_remediate()
                except Exception as e:
                    logger.error(f"Remediation loop error: {e}")
                time.sleep(interval_seconds)
        self._worker = threading.Thread(target=loop, daemon=True)
        self._worker.start()
        logger.info("Auto‑remediation engine started")
    
    def stop(self):
        self._running = False
        if self._worker:
            self._worker.join(timeout=5)
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        return self.remediation_history[-limit:]
    
    def get_status(self) -> Dict:
        return {
            "running": self._running,
            "policies_enabled": sum(1 for p in self.config["policies"] if p["enabled"]),
            "total_remediations": len(self.remediation_history),
            "last_remediation": self.remediation_history[-1] if self.remediation_history else None
        }

_remediation_engine = None
def get_remediation_engine():
    global _remediation_engine
    if _remediation_engine is None:
        _remediation_engine = RemediationEngine()
    return _remediation_engine
