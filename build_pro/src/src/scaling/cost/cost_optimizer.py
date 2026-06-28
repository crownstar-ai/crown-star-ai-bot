# scaling/cost/cost_optimizer.py – Cost optimisation policies
import time
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List

class CostOptimizer:
    def __init__(self):
        self.idle_detection_window = deque(maxlen=60)  # 60 minutes
        self.idle_threshold = 0.05  # 5% load threshold
        self.idle_minutes_required = 30
        self.rightsizing_enabled = True
        self.spot_fallback_enabled = True
    
    def record_load(self, load: float):
        self.idle_detection_window.append((datetime.utcnow(), load))
    
    def is_idle(self) -> bool:
        """Check if system has been idle for `idle_minutes_required` minutes"""
        if len(self.idle_detection_window) < self.idle_minutes_required:
            return False
        recent = list(self.idle_detection_window)[-self.idle_minutes_required:]
        avg_load = sum(l for _, l in recent) / len(recent)
        return avg_load < self.idle_threshold
    
    def get_rightsizing_recommendation(self, current_cpu: float, current_memory: float) -> Dict:
        """Recommend downsizing CPU/memory limits based on historical usage"""
        recommendation = {
            "scale_down_cpu": False,
            "scale_down_memory": False,
            "recommended_cpu": current_cpu,
            "recommended_memory": current_memory,
            "reason": ""
        }
        if current_cpu < 0.2:  # less than 20% utilisation
            recommendation["scale_down_cpu"] = True
            recommendation["recommended_cpu"] = max(0.5, current_cpu * 0.7)
            recommendation["reason"] = "CPU underutilised"
        if current_memory < 0.3:
            recommendation["scale_down_memory"] = True
            recommendation["recommended_memory"] = max(0.5, current_memory * 0.8)
        return recommendation
    
    def should_use_spot_instances(self, workload_type: str = "api") -> bool:
        """Determine if workload can tolerate spot interruption"""
        # API workloads require stability – use on-demand
        if workload_type == "api":
            return False
        # Batch/async workers can use spot
        if workload_type == "worker":
            return True
        # Analytics background jobs can use spot
        if workload_type == "analytics":
            return True
        return False
    
    def generate_optimization_report(self) -> Dict:
        return {
            "is_idle": self.is_idle(),
            "idle_minutes": len(self.idle_detection_window),
            "rightsizing_enabled": self.rightsizing_enabled,
            "spot_fallback_enabled": self.spot_fallback_enabled,
            "timestamp": datetime.utcnow().isoformat()
        }

# Global instance
_cost_optimizer = None
def get_cost_optimizer():
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = CostOptimizer()
    return _cost_optimizer
