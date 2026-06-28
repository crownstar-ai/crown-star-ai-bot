# chaos/service.py – Chaos engineering fault injection engine
import time
import random
import threading
import os
import psutil
import subprocess
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import signal

@dataclass
class ChaosExperiment:
    id: str
    name: str
    type: str  # latency, error, memory, cpu, network, pod_kill
    target: str  # api, worker, database, cache
    duration: int  # seconds
    intensity: float  # 0.0-1.0 or specific value
    status: str = "pending"  # pending, running, stopped, completed
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

class ChaosEngine:
    def __init__(self, config_path: str = "config/chaos/config.json"):
        self.config = self._load_config(config_path)
        self.active_experiments: Dict[str, ChaosExperiment] = {}
        self.experiment_history: List[ChaosExperiment] = []
        self._lock = threading.Lock()
        self._safe_mode = self.config.get("safe_mode", True)
        self._injectors = {
            "latency": self._inject_latency,
            "error": self._inject_error,
            "memory": self._inject_memory_pressure,
            "cpu": self._inject_cpu_spike,
            "network": self._inject_network_partition,
            "pod_kill": self._inject_pod_kill
        }
    
    def _load_config(self, path):
        default = {
            "safe_mode": True,  # prevent chaos in production
            "default_duration": 30,
            "allowed_experiments": ["latency", "error", "memory", "cpu"],
            "max_concurrent": 3,
            "pod_kill_namespace": "crownstar",
            "pod_kill_selector": "app=crownstar-api"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {**default, **json.load(f)}
        return default
    
    def is_safe_mode(self) -> bool:
        return self._safe_mode
    
    def set_safe_mode(self, enabled: bool):
        self._safe_mode = enabled
        if enabled:
            self.stop_all_experiments()
    
    def start_experiment(self, exp_type: str, target: str = "api", duration: int = None, intensity: float = 0.5) -> Optional[str]:
        if self._safe_mode:
            return None
        if exp_type not in self._injectors:
            raise ValueError(f"Unknown experiment type: {exp_type}")
        if len(self.active_experiments) >= self.config.get("max_concurrent", 3):
            raise RuntimeError("Max concurrent experiments reached")
        
        exp_id = f"{exp_type}_{int(time.time())}"
        exp = ChaosExperiment(
            id=exp_id,
            name=f"{exp_type}_on_{target}",
            type=exp_type,
            target=target,
            duration=duration or self.config.get("default_duration", 30),
            intensity=intensity
        )
        with self._lock:
            self.active_experiments[exp_id] = exp
            self.experiment_history.append(exp)
        exp.status = "running"
        exp.started_at = time.time()
        
        # Start injection in background
        thread = threading.Thread(target=self._run_experiment, args=(exp,), daemon=True)
        thread.start()
        return exp_id
    
    def _run_experiment(self, exp: ChaosExperiment):
        injector = self._injectors.get(exp.type)
        if not injector:
            return
        try:
            injector(exp)
            time.sleep(exp.duration)
        finally:
            self.stop_experiment(exp.id)
    
    def stop_experiment(self, exp_id: str) -> bool:
        with self._lock:
            if exp_id not in self.active_experiments:
                return False
            exp = self.active_experiments[exp_id]
            exp.status = "stopped"
            exp.stopped_at = time.time()
            # Call cleanup for active injectors if needed
            if exp.type == "memory":
                self._cleanup_memory_pressure()
            elif exp.type == "cpu":
                self._cleanup_cpu_spike()
            elif exp.type == "network":
                self._cleanup_network_partition()
            del self.active_experiments[exp_id]
        return True
    
    def stop_all_experiments(self):
        for exp_id in list(self.active_experiments.keys()):
            self.stop_experiment(exp_id)
    
    def get_status(self) -> Dict:
        return {
            "safe_mode": self._safe_mode,
            "active_experiments": [
                {"id": e.id, "type": e.type, "target": e.target, "duration_remaining": max(0, e.duration - (time.time() - e.started_at))}
                for e in self.active_experiments.values()
            ],
            "history_count": len(self.experiment_history)
        }
    
    # ---------- Injectors ----------
    def _inject_latency(self, exp: ChaosExperiment):
        # Set global latency multiplier (used by middleware)
        latency_ms = int(exp.intensity * 5000)  # up to 5 seconds
        os.environ["CHAOS_LATENCY_MS"] = str(latency_ms)
        time.sleep(exp.duration)
        os.environ.pop("CHAOS_LATENCY_MS", None)
    
    def _inject_error(self, exp: ChaosExperiment):
        # Set error rate (0.0-1.0)
        error_rate = exp.intensity
        os.environ["CHAOS_ERROR_RATE"] = str(error_rate)
        time.sleep(exp.duration)
        os.environ.pop("CHAOS_ERROR_RATE", None)
    
    def _inject_memory_pressure(self, exp: ChaosExperiment):
        # Allocate large memory chunk
        size_mb = int(exp.intensity * 500)  # up to 500 MB
        self._memory_block = bytearray(size_mb * 1024 * 1024)
        time.sleep(exp.duration)
        self._memory_block = None
    
    def _cleanup_memory_pressure(self):
        self._memory_block = None
        import gc
        gc.collect()
    
    def _inject_cpu_spike(self, exp: ChaosExperiment):
        # Spin CPU for duration
        end = time.time() + exp.duration
        def cpu_loop():
            while time.time() < end:
                _ = 123456789 * 987654321
        self._cpu_thread = threading.Thread(target=cpu_loop, daemon=True)
        self._cpu_thread.start()
    
    def _cleanup_cpu_spike(self):
        # Thread will die when duration ends; no explicit cleanup needed
        pass
    
    def _inject_network_partition(self, exp: ChaosExperiment):
        # Simulate network partition by blocking egress (requires iptables)
        try:
            subprocess.run(["iptables", "-A", "OUTPUT", "-j", "DROP", "-d", "10.0.0.0/8"], check=False, timeout=5)
            self._network_rules_applied = True
        except:
            pass
        time.sleep(exp.duration)
        if hasattr(self, "_network_rules_applied"):
            subprocess.run(["iptables", "-D", "OUTPUT", "-j", "DROP", "-d", "10.0.0.0/8"], check=False, timeout=5)
    
    def _cleanup_network_partition(self):
        pass
    
    def _inject_pod_kill(self, exp: ChaosExperiment):
        # Kill Kubernetes pod (requires kubectl)
        namespace = self.config.get("pod_kill_namespace", "crownstar")
        selector = self.config.get("pod_kill_selector", "app=crownstar-api")
        try:
            subprocess.run(["kubectl", "delete", "pod", "-l", selector, "-n", namespace], check=False, timeout=10)
        except:
            pass
        # No need to wait – pod kill is instant
        exp.duration = 1  # short

# Global instance
_chaos_engine = None
def get_chaos_engine():
    global _chaos_engine
    if _chaos_engine is None:
        _chaos_engine = ChaosEngine()
    return _chaos_engine
