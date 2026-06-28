# chaos/scenarios.py – Pre‑defined chaos experiments
import json
from .service import get_chaos_engine

def run_scenario(name: str, duration: int = 60):
    engine = get_chaos_engine()
    scenarios = {
        "latency_spike": ("latency", 0.8, "api"),
        "error_burst": ("error", 0.3, "api"),
        "memory_pressure": ("memory", 0.6, "api"),
        "cpu_hammer": ("cpu", 0.9, "api")
    }
    if name not in scenarios:
        raise ValueError(f"Unknown scenario: {name}")
    typ, intensity, target = scenarios[name]
    return engine.start_experiment(typ, target, duration, intensity)

def list_scenarios():
    return ["latency_spike", "error_burst", "memory_pressure", "cpu_hammer"]
