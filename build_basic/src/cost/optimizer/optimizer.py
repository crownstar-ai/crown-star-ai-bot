# cost/optimizer/optimizer.py – CrownStar Cost Optimization Engine
import json, os, time, datetime, hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import requests
import threading
import queue

@dataclass
class ResourceMetrics:
    resource_id: str
    resource_type: str   # compute, storage, network
    provider: str        # aws, azure, gcp, sovereign
    region: str
    hourly_cost: float
    utilization_cpu: float
    utilization_memory: float
    utilization_disk: float
    timestamp: int

@dataclass
class CostRecommendation:
    recommendation_id: str
    resource_id: str
    action: str            # rightsize, delete, tier_down, reserved, spot, storage_tier
    current_cost_monthly: float
    projected_cost_monthly: float
    savings_monthly: float
    confidence: float
    details: Dict
    created_at: int

class CostOptimizer:
    def __init__(self, config_path="config/cost/optimizer.json"):
        self.config = self._load_config(config_path)
        self.metrics_queue = queue.Queue()
        self.recommendations = {}
        self._load_providers()

    def _load_config(self, path):
        default = {
            "providers": ["aws", "azure", "gcp", "sovereign"],
            "preferred_regions": ["ap-southeast-2", "australiaeast", "australia-southeast1"],
            "compute_utilization_target": 0.6,
            "storage_unused_threshold_days": 30,
            "spot_allowed": True,
            "reserved_instance_lookahead_months": 12,
            "alert_on_savings_threshold": 100.0
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def _load_providers(self):
        self.provider_clients = {}
        # in real system: boto3, azure-mgmt-costmanagement, google-cloud-billing
        # Placeholder – we simulate reading from CloudWatch / Azure Monitor / GCP metrics
        self.provider_clients["aws"] = AWSSimulator()
        self.provider_clients["azure"] = AzureSimulator()
        self.provider_clients["gcp"] = GCPSimulator()
        self.provider_clients["sovereign"] = SovereignSimulator()

    def ingest_metrics(self, metrics: ResourceMetrics):
        self.metrics_queue.put(metrics)

    def run_optimization_cycle(self):
        """Periodic full optimization (called by scheduler)"""
        all_metrics = self._collect_recent_metrics()
        # 1. Compute rightsizing
        rightsizing = self._recommend_rightsizing(all_metrics)
        # 2. Storage optimization
        storage_opt = self._recommend_storage_tiering(all_metrics)
        # 3. Reserved / spot recommendations
        reservation = self._recommend_reservations(all_metrics)
        # 4. Orphaned resources
        orphaned = self._find_orphaned_resources(all_metrics)

        all_recs = rightsizing + storage_opt + reservation + orphaned
        for rec in all_recs:
            self.recommendations[rec.recommendation_id] = rec
        return all_recs

    def _collect_recent_metrics(self) -> List[ResourceMetrics]:
        # Simplified: read from /data/cost/metrics/*.json
        collected = []
        metrics_dir = "data/cost/metrics"
        if os.path.exists(metrics_dir):
            for fname in os.listdir(metrics_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(metrics_dir, fname), 'r') as f:
                        data = json.load(f)
                        collected.append(ResourceMetrics(**data))
        return collected

    def _recommend_rightsizing(self, metrics: List[ResourceMetrics]) -> List[CostRecommendation]:
        recs = []
        for m in metrics:
            if m.resource_type != "compute":
                continue
            # If CPU utilization <20% for a week, recommend downsizing
            if m.utilization_cpu < 0.2:
                savings = m.hourly_cost * 730 * 0.6  # assume 60% cheaper instance
                rec = CostRecommendation(
                    recommendation_id = hashlib.md5(f"{m.resource_id}_rightsize".encode()).hexdigest()[:16],
                    resource_id = m.resource_id,
                    action = "rightsize_down",
                    current_cost_monthly = m.hourly_cost * 730,
                    projected_cost_monthly = m.hourly_cost * 730 * 0.4,
                    savings_monthly = savings,
                    confidence = 0.9,
                    details = {"reason": f"CPU util {m.utilization_cpu*100:.1f}% < 20%", "suggested": "smaller instance family"},
                    created_at = int(time.time())
                )
                recs.append(rec)
            elif m.utilization_cpu > 0.8:
                savings = 0  # upsizing not a saving
                rec = CostRecommendation(
                    recommendation_id = hashlib.md5(f"{m.resource_id}_upsize".encode()).hexdigest()[:16],
                    resource_id = m.resource_id,
                    action = "rightsize_up",
                    current_cost_monthly = m.hourly_cost * 730,
                    projected_cost_monthly = m.hourly_cost * 730 * 1.5,
                    savings_monthly = 0,
                    confidence = 0.7,
                    details = {"reason": f"CPU util {m.utilization_cpu*100:.1f}% > 80%", "suggested": "larger instance family"},
                    created_at = int(time.time())
                )
                recs.append(rec)
        return recs

    def _recommend_storage_tiering(self, metrics: List[ResourceMetrics]) -> List[CostRecommendation]:
        recs = []
        for m in metrics:
            if m.resource_type != "storage":
                continue
            # If disk utilization < 10% and data older than threshold, recommend cold/archive
            if m.utilization_disk < 0.1:
                savings = m.hourly_cost * 730 * 0.7  # cold tier ~30% of cost
                rec = CostRecommendation(
                    recommendation_id = hashlib.md5(f"{m.resource_id}_storage".encode()).hexdigest()[:16],
                    resource_id = m.resource_id,
                    action = "storage_tier_cold",
                    current_cost_monthly = m.hourly_cost * 730,
                    projected_cost_monthly = m.hourly_cost * 730 * 0.3,
                    savings_monthly = savings,
                    confidence = 0.85,
                    details = {"reason": f"Disk util {m.utilization_disk*100:.1f}% < 10%", "tier": "cold"},
                    created_at = int(time.time())
                )
                recs.append(rec)
        return recs

    def _recommend_reservations(self, metrics: List[ResourceMetrics]) -> List[CostRecommendation]:
        # Placeholder: if a resource has > 80% utilization for 30 days, recommend 1-year reserved
        recs = []
        # Simple simulation
        return recs

    def _find_orphaned_resources(self, metrics: List[ResourceMetrics]) -> List[CostRecommendation]:
        recs = []
        # Resources with zero activity for 7 days
        for m in metrics:
            if m.utilization_cpu == 0 and m.utilization_memory == 0 and time.time() - m.timestamp > 7*86400:
                rec = CostRecommendation(
                    recommendation_id = hashlib.md5(f"{m.resource_id}_orphan".encode()).hexdigest()[:16],
                    resource_id = m.resource_id,
                    action = "delete",
                    current_cost_monthly = m.hourly_cost * 730,
                    projected_cost_monthly = 0,
                    savings_monthly = m.hourly_cost * 730,
                    confidence = 0.95,
                    details = {"reason": "No activity for 7 days"},
                    created_at = int(time.time())
                )
                recs.append(rec)
        return recs

    def get_recommendations(self, limit=50) -> List[Dict]:
        sorted_recs = sorted(self.recommendations.values(), key=lambda x: x.savings_monthly, reverse=True)
        return [asdict(r) for r in sorted_recs[:limit]]

    def forecast_cost(self, days=30) -> Dict:
        # Simple linear forecast based on previous 30 days trend
        metrics_dir = "data/cost/metrics"
        daily_costs = {}
        for fname in os.listdir(metrics_dir):
            if fname.endswith(".json"):
                with open(os.path.join(metrics_dir, fname), 'r') as f:
                    data = json.load(f)
                    day = datetime.datetime.fromtimestamp(data["timestamp"]).strftime("%Y-%m-%d")
                    daily_costs[day] = daily_costs.get(day, 0) + data["hourly_cost"] * 24
        if not daily_costs:
            return {"forecast": [], "error": "no data"}
        # average growth
        days_list = sorted(daily_costs.keys())
        if len(days_list) < 2:
            return {"forecast": [{"date": (datetime.datetime.now()+datetime.timedelta(days=i)).strftime("%Y-%m-%d"), "cost": sum(daily_costs.values())/len(days_list)} for i in range(days)]}
        first_cost = daily_costs[days_list[0]]
        last_cost = daily_costs[days_list[-1]]
        trend = (last_cost - first_cost) / max(1, len(days_list))
        forecast = []
        last_date = datetime.datetime.strptime(days_list[-1], "%Y-%m-%d")
        for i in range(1, days+1):
            pred_date = last_date + datetime.timedelta(days=i)
            pred_cost = last_cost + trend * i
            forecast.append({"date": pred_date.strftime("%Y-%m-%d"), "cost": round(pred_cost, 2)})
        return {"forecast": forecast, "trend_per_day": trend, "base_daily": last_cost}

# Simulators for providers (stubs)
class AWSSimulator: pass
class AzureSimulator: pass
class GCPSimulator: pass
class SovereignSimulator: pass

_optimizer = None
def get_optimizer():
    global _optimizer
    if _optimizer is None:
        _optimizer = CostOptimizer()
    return _optimizer
