# flags/core.py – CrownStar A/B Testing & Feature Flag Engine
import os, json, time, hashlib, random, threading, uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
import logging
import math

logger = logging.getLogger(__name__)

class FlagType(Enum):
    BOOLEAN = "boolean"; STRING = "string"; NUMBER = "number"; JSON = "json"

class FlagKind(Enum):
    FEATURE_FLAG = "feature_flag"; EXPERIMENT = "experiment"

class RolloutStrategy(Enum):
    RANDOM = "random"; HASH = "hash"; PERCENTAGE = "percentage"

@dataclass
class FlagDefinition:
    key: str; name: str; flag_type: FlagType; kind: FlagKind; default_value: Any
    enabled: bool = True; rollout_strategy: RolloutStrategy = RolloutStrategy.HASH
    rules: List[Dict] = None; variants: Dict[str, Any] = None; rollout_percentage: float = 100.0
    created_at: int = 0; updated_at: int = 0; description: str = ""

@dataclass
class EvaluationContext:
    user_id: str; email: Optional[str] = None; country: Optional[str] = None
    tier: Optional[str] = None; custom: Dict = None

@dataclass
class EvaluationResult:
    flag_key: str; value: Any; variant: Optional[str]; reason: str; timestamp: int

@dataclass
class ExperimentAssignment:
    user_id: str; experiment_key: str; variant: str; allocated_at: int

class TargetingEngine:
    def evaluate_rule(self, rule: Dict, context: EvaluationContext) -> bool:
        attr = rule.get("attr"); op = rule.get("op"); values = rule.get("values")
        if not attr or not op: return True
        if attr == "user_id": val = context.user_id
        elif attr == "email": val = context.email
        elif attr == "country": val = context.country
        elif attr == "tier": val = context.tier
        else: val = context.custom.get(attr) if context.custom else None
        if op == "in": return val in (values or [])
        if op == "not_in": return val not in (values or [])
        if op == "eq": return val == values[0] if values else False
        if op == "neq": return val != values[0] if values else False
        if op == "regex": import re; return bool(re.match(values[0], str(val))) if values else False
        if op == "gt": return float(val) > float(values[0]) if values else False
        if op == "lt": return float(val) < float(values[0]) if values else False
        return True

    def evaluate_targeting(self, flag: FlagDefinition, context: EvaluationContext) -> bool:
        if not flag.rules: return True
        for rule_group in flag.rules:
            if isinstance(rule_group, list):
                if not any(self.evaluate_rule(rule, context) for rule in rule_group): return False
            else:
                if not self.evaluate_rule(rule_group, context): return False
        return True

class RolloutEngine:
    @staticmethod
    def get_bucket(user_id: str, key: str, total_buckets: int = 100) -> int:
        hash_input = f"{user_id}:{key}"
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
        return hash_val % total_buckets

    @staticmethod
    def is_enabled_for_user(flag: FlagDefinition, context: EvaluationContext) -> bool:
        if flag.rollout_strategy == RolloutStrategy.HASH:
            bucket = RolloutEngine.get_bucket(context.user_id, flag.key)
            return bucket < (flag.rollout_percentage / 100.0 * 100)
        elif flag.rollout_strategy == RolloutStrategy.RANDOM:
            return random.random() < (flag.rollout_percentage / 100.0)
        return True

class FlagStore:
    def __init__(self, storage_dir="data/flags"):
        self.storage_dir = storage_dir
        self.flags: Dict[str, FlagDefinition] = {}
        self.audit_log: List[Dict] = []
        os.makedirs(storage_dir, exist_ok=True)
        self._load()

    def _load(self):
        flags_path = os.path.join(self.storage_dir, "flags.json")
        if os.path.exists(flags_path):
            with open(flags_path, 'r') as f:
                data = json.load(f)
                for key, d in data.items():
                    d["flag_type"] = FlagType(d["flag_type"])
                    d["kind"] = FlagKind(d["kind"])
                    d["rollout_strategy"] = RolloutStrategy(d.get("rollout_strategy", "hash"))
                    self.flags[key] = FlagDefinition(**d)

    def _save(self):
        flags_data = {}
        for key, flag in self.flags.items():
            d = asdict(flag)
            d["flag_type"] = flag.flag_type.value
            d["kind"] = flag.kind.value
            d["rollout_strategy"] = flag.rollout_strategy.value
            flags_data[key] = d
        with open(os.path.join(self.storage_dir, "flags.json"), 'w') as f:
            json.dump(flags_data, f, indent=2)

    def put(self, flag: FlagDefinition):
        flag.updated_at = int(time.time())
        if flag.created_at == 0: flag.created_at = flag.updated_at
        self.flags[flag.key] = flag
        self._save()
        self._log_audit("update", flag.key, flag)

    def get(self, key: str) -> Optional[FlagDefinition]: return self.flags.get(key)
    def delete(self, key: str) -> bool:
        if key in self.flags:
            del self.flags[key]
            self._save()
            self._log_audit("delete", key, None)
            return True
        return False
    def list(self) -> List[FlagDefinition]: return list(self.flags.values())

    def _log_audit(self, action: str, key: str, flag: Optional[FlagDefinition]):
        entry = {"action": action, "key": key, "timestamp": int(time.time()), "flag": asdict(flag) if flag else None}
        self.audit_log.append(entry)
        if len(self.audit_log) > 1000: self.audit_log = self.audit_log[-500:]
        audit_path = os.path.join(self.storage_dir, "audit.json")
        with open(audit_path, 'w') as f: json.dump(self.audit_log, f, indent=2)

class ExperimentManager:
    def __init__(self, flag_store: FlagStore):
        self.store = flag_store
        self.assignments: Dict[str, ExperimentAssignment] = {}
        self._lock = threading.Lock()

    def allocate_variant(self, experiment: FlagDefinition, context: EvaluationContext) -> str:
        key = experiment.key
        variants = experiment.variants
        if not variants: return "control"
        variant_names = list(variants.keys())
        if len(variant_names) == 0: return "control"
        bucket = RolloutEngine.get_bucket(context.user_id, f"exp_{key}", 100)
        step = 100 // len(variant_names)
        idx = min(bucket // step, len(variant_names)-1)
        variant = variant_names[idx]
        assignment_key = f"{context.user_id}:{key}"
        with self._lock:
            if assignment_key not in self.assignments:
                self.assignments[assignment_key] = ExperimentAssignment(user_id=context.user_id, experiment_key=key, variant=variant, allocated_at=int(time.time()))
            else:
                variant = self.assignments[assignment_key].variant
        return variant

    def get_variant_value(self, experiment: FlagDefinition, variant: str) -> Any:
        return experiment.variants.get(variant, experiment.default_value)

    def track_conversion(self, experiment_key: str, user_id: str, event_name: str):
        assignment_key = f"{user_id}:{experiment_key}"
        assignment = self.assignments.get(assignment_key)
        if not assignment: return
        metric_key = f"{experiment_key}:{assignment.variant}:{event_name}"
        # simplified – no persistent storage needed for demo

    def get_experiment_results(self, experiment_key: str) -> Dict:
        # simplified for demo
        return {}

class FeatureFlagManager:
    def __init__(self, config_path="config/flags/config.json"):
        self.config = self._load_config(config_path)
        self.store = FlagStore()
        self.targeting = TargetingEngine()
        self.rollout = RolloutEngine()
        self.experiment = ExperimentManager(self.store)
        self._evaluation_history: List[EvaluationResult] = []

    def _load_config(self, path):
        default = {"default_rollout_percentage": 100, "cache_ttl_seconds": 5, "metrics_enabled": True}
        if os.path.exists(path):
            with open(path, 'r') as f: default.update(json.load(f))
        return default

    def create_flag(self, flag: FlagDefinition) -> str: self.store.put(flag); return flag.key
    def update_flag(self, flag: FlagDefinition) -> bool:
        existing = self.store.get(flag.key)
        if not existing: return False
        flag.created_at = existing.created_at
        self.store.put(flag); return True
    def delete_flag(self, key: str) -> bool: return self.store.delete(key)
    def get_flag(self, key: str) -> Optional[FlagDefinition]: return self.store.get(key)
    def list_flags(self) -> List[FlagDefinition]: return self.store.list()

    def evaluate(self, key: str, context: EvaluationContext) -> EvaluationResult:
        flag = self.store.get(key)
        if not flag: return EvaluationResult(flag_key=key, value=None, variant=None, reason=f"Flag {key} not found", timestamp=int(time.time()))
        if not flag.enabled: return EvaluationResult(flag_key=key, value=flag.default_value, variant=None, reason="Flag disabled", timestamp=int(time.time()))
        if not self.targeting.evaluate_targeting(flag, context):
            return EvaluationResult(flag_key=key, value=flag.default_value, variant=None, reason="Targeting rule not matched", timestamp=int(time.time()))
        if not self.rollout.is_enabled_for_user(flag, context):
            return EvaluationResult(flag_key=key, value=flag.default_value, variant=None, reason="Rollout percentage not met", timestamp=int(time.time()))
        if flag.kind == FlagKind.EXPERIMENT:
            variant = self.experiment.allocate_variant(flag, context)
            value = self.experiment.get_variant_value(flag, variant)
            result = EvaluationResult(flag_key=key, value=value, variant=variant, reason="Experiment variant assigned", timestamp=int(time.time()))
        else:
            result = EvaluationResult(flag_key=key, value=flag.default_value, variant=None, reason="Flag enabled", timestamp=int(time.time()))
        if self.config["metrics_enabled"]:
            self._evaluation_history.append(result)
            if len(self._evaluation_history) > 10000: self._evaluation_history = self._evaluation_history[-5000:]
        return result

    def track_conversion(self, experiment_key: str, user_id: str, event_name: str):
        self.experiment.track_conversion(experiment_key, user_id, event_name)

    def get_experiment_results(self, experiment_key: str) -> Dict:
        return self.experiment.get_experiment_results(experiment_key)

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        return self.store.audit_log[-limit:]

_flags_manager = None
def get_flags_manager():
    global _flags_manager
    if _flags_manager is None: _flags_manager = FeatureFlagManager()
    return _flags_manager
