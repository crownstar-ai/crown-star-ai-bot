# routing/core.py – CrownStar Cost‑Aware Routing & Load Balancing Engine
import os, json, time, random, threading, heapq, hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import requests

logger = logging.getLogger(__name__)

class RoutingPolicy(Enum):
    LEAST_COST = "least_cost"
    COST_LATENCY = "cost_latency"
    TIME_OF_DAY = "time_of_day"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"

@dataclass
class Endpoint:
    id: str; url: str; provider: str; region: str; instance_type: str
    base_cost_per_hour: float; latency_ms: float; weight: float = 1.0; enabled: bool = True

@dataclass
class RoutingRequest:
    request_id: str; endpoint_id: str; cost: float; latency_ms: float; timestamp: int

@dataclass
class RoutingDecision:
    endpoint_id: str; url: str; reason: str; estimated_cost: float; estimated_latency: float

class CostProvider:
    def __init__(self):
        self._cache = {}; self._cache_ttl = 300
    def get_cost(self, provider: str, region: str, instance_type: str) -> float:
        key = f"{provider}_{region}_{instance_type}"
        now = time.time()
        if key in self._cache and now - self._cache[key]["timestamp"] < self._cache_ttl:
            return self._cache[key]["cost"]
        base = self._get_base_cost(provider, region, instance_type)
        is_spot = random.random() < 0.3
        if is_spot:
            cost = base * (1 - random.uniform(0.3, 0.7))
        else:
            cost = base
        self._cache[key] = {"cost": cost, "timestamp": now}
        return cost
    def _get_base_cost(self, provider: str, region: str, instance_type: str) -> float:
        base = {
            "aws": {"ap-southeast-2": {"t3.micro": 0.0104, "t3.medium": 0.0416, "m5.large": 0.096},
                    "us-east-1": {"t3.micro": 0.0104, "t3.medium": 0.0416, "m5.large": 0.096}},
            "azure": {"australiaeast": {"B2s": 0.032, "B2ms": 0.064, "D2s_v3": 0.096}},
            "gcp": {"australia-southeast1": {"n2-standard-2": 0.096, "n2-standard-4": 0.192}},
            "sovereign_au": {"au-east": {"small": 0.015, "medium": 0.06, "large": 0.15}}
        }
        return base.get(provider, {}).get(region, {}).get(instance_type, 0.05)

class LeastCostPolicy:
    def select(self, endpoints, cost_provider):
        best = None; best_cost = float('inf')
        for ep in endpoints:
            if not ep.enabled: continue
            cost = cost_provider.get_cost(ep.provider, ep.region, ep.instance_type)
            if cost < best_cost:
                best_cost = cost; best = ep
        return best

class CostLatencyPolicy:
    def __init__(self, cost_weight=0.5, latency_weight=0.5):
        self.cost_weight = cost_weight; self.latency_weight = latency_weight
    def select(self, endpoints, cost_provider):
        scores = []
        for ep in endpoints:
            if not ep.enabled: continue
            cost = cost_provider.get_cost(ep.provider, ep.region, ep.instance_type)
            cost_norm = min(1.0, cost / 1.0)
            latency_norm = min(1.0, ep.latency_ms / 500.0)
            score = (1 - cost_norm) * self.cost_weight + (1 - latency_norm) * self.latency_weight
            scores.append((score, ep))
        if not scores: return None
        return max(scores, key=lambda x: x[0])[1]

class TimeOfDayPolicy:
    def __init__(self, cost_provider):
        self.cost_provider = cost_provider
        self.off_peak_hours = range(2, 6)
    def select(self, endpoints):
        local_hour = datetime.now().hour
        is_off_peak = local_hour in self.off_peak_hours
        if is_off_peak:
            return LeastCostPolicy().select(endpoints, self.cost_provider)
        else:
            best = None; best_cost = float('inf')
            for ep in endpoints:
                if not ep.enabled: continue
                multiplier = 1.2 if ep.region in ["us-east-1","ap-southeast-2"] else 1.0
                cost = self.cost_provider.get_cost(ep.provider, ep.region, ep.instance_type) * multiplier
                if cost < best_cost:
                    best_cost = cost; best = ep
            return best

class WeightedPolicy:
    def select(self, endpoints, cost_provider):
        total_weight = 0.0; weights = []
        for ep in endpoints:
            if not ep.enabled:
                weights.append(0.0); continue
            cost = cost_provider.get_cost(ep.provider, ep.region, ep.instance_type)
            w = 1.0 / (cost + 0.001)
            weights.append(w); total_weight += w
        if total_weight == 0: return None
        r = random.uniform(0, total_weight); cum = 0.0
        for ep, w in zip(endpoints, weights):
            cum += w
            if r <= cum: return ep
        return endpoints[0] if endpoints else None

class CostAwareBalancer:
    def __init__(self, config_path="config/routing/balancer.json"):
        self.config = self._load_config(config_path)
        self.endpoints: Dict[str, Endpoint] = {}
        self.cost_provider = CostProvider()
        self.policies = {
            RoutingPolicy.LEAST_COST: LeastCostPolicy(),
            RoutingPolicy.COST_LATENCY: CostLatencyPolicy(self.config.get("cost_weight",0.5), self.config.get("latency_weight",0.5)),
            RoutingPolicy.TIME_OF_DAY: TimeOfDayPolicy(self.cost_provider),
            RoutingPolicy.WEIGHTED: WeightedPolicy()
        }
        self.current_policy = RoutingPolicy(self.config.get("default_policy","least_cost"))
        self._requests_log = []
        self._load_endpoints()
    def _load_config(self, path):
        default = {"default_policy":"least_cost","cost_weight":0.6,"latency_weight":0.4,"health_check_interval":30,"sync_interval":60,"endpoints":[]}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        return default
    def _load_endpoints(self):
        for ep_cfg in self.config.get("endpoints",[]):
            ep = Endpoint(**ep_cfg)
            self.endpoints[ep.id] = ep
    def set_policy(self, policy_name):
        try:
            self.current_policy = RoutingPolicy(policy_name); return True
        except: return False
    def route_request(self, context=None):
        policy = self.policies[self.current_policy]
        endpoints_list = list(self.endpoints.values())
        selected = policy.select(endpoints_list, self.cost_provider)
        if not selected:
            return RoutingDecision("","","No endpoints available",0.0,0.0)
        cost = self.cost_provider.get_cost(selected.provider, selected.region, selected.instance_type)
        decision = RoutingDecision(selected.id, selected.url, f"Selected by {self.current_policy.value}", cost, selected.latency_ms)
        req = RoutingRequest(hashlib.md5(f"{time.time()}_{random.random()}".encode()).hexdigest()[:16], selected.id, cost, selected.latency_ms, int(time.time()))
        self._requests_log.append(req)
        if len(self._requests_log)>10000: self._requests_log = self._requests_log[-5000:]
        return decision
    def add_endpoint(self, endpoint):
        self.endpoints[endpoint.id]=endpoint; self._save_endpoints(); return True
    def remove_endpoint(self, endpoint_id):
        if endpoint_id in self.endpoints: del self.endpoints[endpoint_id]; self._save_endpoints(); return True
        return False
    def enable_endpoint(self, endpoint_id, enabled):
        if endpoint_id in self.endpoints: self.endpoints[endpoint_id].enabled=enabled; self._save_endpoints(); return True
        return False
    def _save_endpoints(self):
        cfg = self.config.copy()
        cfg["endpoints"] = [asdict(ep) for ep in self.endpoints.values()]
        os.makedirs("config/routing", exist_ok=True)
        with open("config/routing/balancer.json",'w') as f: json.dump(cfg,f,indent=2)
    def get_stats(self):
        stats = {}
        for ep_id in self.endpoints: stats[ep_id] = {"requests":0,"total_cost":0.0}
        for req in self._requests_log:
            if req.endpoint_id in stats:
                stats[req.endpoint_id]["requests"] += 1
                stats[req.endpoint_id]["total_cost"] += req.cost
        return {"policy":self.current_policy.value, "endpoints":stats}
    def optimize_weights(self, learning_rate=0.01):
        avg_costs = {}; counts = {}
        for req in self._requests_log[-1000:]:
            avg_costs[req.endpoint_id] = avg_costs.get(req.endpoint_id,0.0) + req.cost
            counts[req.endpoint_id] = counts.get(req.endpoint_id,0) + 1
        for ep_id in avg_costs: avg_costs[ep_id] /= counts[ep_id]
        min_cost = min(avg_costs.values()) if avg_costs else 0.1
        for ep_id, avg_cost in avg_costs.items():
            if ep_id in self.endpoints:
                new_weight = 1.0 / (max(0.01, avg_cost / max(min_cost,0.01)))
                old_weight = self.endpoints[ep_id].weight
                self.endpoints[ep_id].weight = old_weight*(1-learning_rate) + new_weight*learning_rate
        self._save_endpoints()

_routing_balancer = None
def get_routing_balancer():
    global _routing_balancer
    if _routing_balancer is None:
        _routing_balancer = CostAwareBalancer()
        def _optimise_loop():
            while True:
                time.sleep(300)
                _routing_balancer.optimize_weights()
        threading.Thread(target=_optimise_loop, daemon=True).start()
    return _routing_balancer
