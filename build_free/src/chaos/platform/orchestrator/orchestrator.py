# chaos/platform/orchestrator/orchestrator.py – Unified chaos platform
import json
import os
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from ..chaos_mesh.client import get_chaos_mesh_client
from ..gremlin.client import get_gremlin_client

class ChaosOrchestrator:
    def __init__(self, config_path: str = "config/chaos/platform/config.json"):
        self.config = self._load_config(config_path)
        self.provider = self.config.get("default_provider", "chaos_mesh")
        self.chaos_mesh = get_chaos_mesh_client()
        self.gremlin = get_gremlin_client()
        self.experiments = {}  # in‑memory tracking
    
    def _load_config(self, path):
        import json, os
        default = {
            "default_provider": "chaos_mesh",
            "chaos_mesh": {"namespace": "chaos-testing", "api_url": "http://chaos-mesh:2333"},
            "gremlin": {"team_id": "", "api_key": ""}
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def run_scenario(self, provider: str, scenario_type: str, target: Dict, duration_seconds: int, parameters: Dict = None) -> Dict:
        exp_id = str(uuid.uuid4())[:8]
        if provider == "chaos_mesh":
            result = self._run_chaos_mesh(scenario_type, target, duration_seconds, parameters)
        elif provider == "gremlin":
            result = self._run_gremlin(scenario_type, target, duration_seconds, parameters)
        else:
            return {"error": f"Unknown provider: {provider}"}
        self.experiments[exp_id] = {
            "id": exp_id,
            "provider": provider,
            "scenario_type": scenario_type,
            "target": target,
            "parameters": parameters,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running",
            "result": result
        }
        return {"experiment_id": exp_id, "result": result}
    
    def _run_chaos_mesh(self, scenario_type: str, target: Dict, duration: int, params: Dict) -> Dict:
        name = f"crownstar-chaos-{int(time.time())}"
        pod_selector = target.get("label_selector", {"app": "crownstar-api"})
        duration_str = f"{duration}s"
        if scenario_type == "pod_kill":
            return self.chaos_mesh.create_pod_chaos(name, "pod-kill", pod_selector, duration_str)
        elif scenario_type == "pod_failure":
            return self.chaos_mesh.create_pod_chaos(name, "pod-failure", pod_selector, duration_str)
        elif scenario_type == "network_latency":
            delay = params.get("latency_ms", 100)
            return self.chaos_mesh.create_network_chaos(name, "delay", pod_selector, duration_str, delay=f"{delay}ms")
        elif scenario_type == "network_loss":
            loss = params.get("loss_percent", 10)
            return self.chaos_mesh.create_network_chaos(name, "loss", pod_selector, duration_str, loss=f"{loss}%")
        elif scenario_type == "cpu_stress":
            workers = params.get("workers", 1)
            return self.chaos_mesh.create_stress_chaos(name, pod_selector, duration_str, cpu_stress=True, cpu_workers=workers)
        elif scenario_type == "memory_stress":
            memory = params.get("memory_mb", 100)
            return self.chaos_mesh.create_stress_chaos(name, pod_selector, duration_str, memory_stress=True, memory_size=f"{memory}MB")
        else:
            return {"error": f"Unsupported Chaos Mesh scenario: {scenario_type}"}
    
    def _run_gremlin(self, scenario_type: str, target: Dict, duration: int, params: Dict) -> Dict:
        target_type = target.get("type", "Container")
        target_ids = target.get("ids", ["crownstar-api"])
        duration_seconds = duration
        if scenario_type == "cpu":
            cpu_percent = params.get("cpu_percent", 100)
            return self.gremlin.create_attack(target_type, target_ids, "cpu", duration_seconds, cpu_percent=cpu_percent)
        elif scenario_type == "memory":
            memory_mb = params.get("memory_mb", 500)
            return self.gremlin.create_attack(target_type, target_ids, "memory", duration_seconds, memory_mb=memory_mb)
        elif scenario_type == "latency":
            latency_ms = params.get("latency_ms", 100)
            return self.gremlin.create_attack(target_type, target_ids, "latency", duration_seconds, latency_ms=latency_ms)
        elif scenario_type == "shutdown":
            return self.gremlin.create_attack(target_type, target_ids, "shutdown", duration_seconds)
        else:
            return {"error": f"Unsupported Gremlin scenario: {scenario_type}"}
    
    def stop_experiment(self, experiment_id: str) -> bool:
        exp = self.experiments.get(experiment_id)
        if not exp:
            return False
        if exp["provider"] == "chaos_mesh":
            # Chaos Mesh experiments are auto‑removed after duration; can't stop easily
            pass
        elif exp["provider"] == "gremlin":
            attack_id = exp["result"].get("id")
            if attack_id:
                return self.gremlin.halt_attack(attack_id)
        return True
    
    def get_status(self, experiment_id: str) -> Optional[Dict]:
        return self.experiments.get(experiment_id)
    
    def list_experiments(self, limit: int = 20) -> List[Dict]:
        return list(self.experiments.values())[-limit:]

_chaos_orchestrator = None
def get_chaos_orchestrator():
    global _chaos_orchestrator
    if _chaos_orchestrator is None:
        _chaos_orchestrator = ChaosOrchestrator()
    return _chaos_orchestrator

import time
