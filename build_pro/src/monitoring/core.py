# monitoring/core.py – CrownStar Model Monitoring & Drift Detection Engine
import os, json, time, numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import deque
from enum import Enum
import logging
import threading
import hashlib

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Enums and Data Models
# --------------------------------------------------------------------
class DriftType(Enum):
    DATA_DRIFT = "data_drift"
    CONCEPT_DRIFT = "concept_drift"
    PERFORMANCE_DRIFT = "performance_drift"

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class DriftReport:
    report_id: str
    model_id: str
    version_id: str
    drift_type: DriftType
    feature_name: Optional[str]
    statistic: str
    value: float
    threshold: float
    severity: AlertSeverity
    timestamp: int
    sample_size: int

@dataclass
class PerformanceSnapshot:
    model_id: str
    version_id: str
    timestamp: int
    accuracy: Optional[float]
    latency_ms: float
    throughput_rps: float
    error_rate: float
    cpu_usage: float
    memory_usage_mb: float

# --------------------------------------------------------------------
# Statistical Drift Detectors
# --------------------------------------------------------------------
class KSDriftDetector:
    @staticmethod
    def compute(reference: np.ndarray, current: np.ndarray) -> float:
        from scipy import stats
        ks_stat, p_value = stats.ks_2samp(reference, current)
        return ks_stat

class PSIDriftDetector:
    @staticmethod
    def compute(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
        quantiles = np.percentile(reference, np.linspace(0, 100, bins+1))
        quantiles[0] = -np.inf
        quantiles[-1] = np.inf
        psi = 0.0
        ref_counts, _ = np.histogram(reference, bins=quantiles)
        cur_counts, _ = np.histogram(current, bins=quantiles)
        ref_pct = ref_counts / len(reference)
        cur_pct = cur_counts / len(current)
        for r, c in zip(ref_pct, cur_pct):
            if r > 0 and c > 0:
                psi += (c - r) * np.log(c / r)
        return psi

class WassersteinDriftDetector:
    @staticmethod
    def compute(reference: np.ndarray, current: np.ndarray) -> float:
        from scipy.stats import wasserstein_distance
        return wasserstein_distance(reference, current)

# --------------------------------------------------------------------
# Concept Drift Detectors (online)
# --------------------------------------------------------------------
class ADWIN:
    def __init__(self, delta: float = 0.002, max_buckets: int = 1000):
        self.delta = delta
        self.max_buckets = max_buckets
        self.buckets = deque()
        self.total = 0.0
        self.count = 0
        self._drift_detected = False

    def add_element(self, value: float):
        self.buckets.append(value)
        self.total += value
        self.count += 1
        self._check_drift()

    def _check_drift(self):
        if self.count < 100:
            return
        n1 = self.count // 2
        n2 = self.count - n1
        mean1 = sum(list(self.buckets)[:n1]) / n1
        mean2 = sum(list(self.buckets)[n1:]) / n2
        epsilon = np.sqrt(1 / (2 * n1) + 1 / (2 * n2)) * np.sqrt(2 * np.log(2 / self.delta))
        if abs(mean1 - mean2) > epsilon:
            self._drift_detected = True
            for _ in range(n1):
                self.buckets.popleft()
            self.count = n2
            self.total = sum(self.buckets)

    def drift_detected(self) -> bool:
        return self._drift_detected

# --------------------------------------------------------------------
# Performance Monitor
# --------------------------------------------------------------------
class PerformanceMonitor:
    def __init__(self, window_size: int = 1000):
        self.snapshots: deque = deque(maxlen=window_size)
        self._control_limits = {}

    def add_snapshot(self, snapshot: PerformanceSnapshot):
        self.snapshots.append(snapshot)

    def compute_control_limits(self, metric: str, n_sigma: float = 3.0):
        values = [getattr(s, metric) for s in self.snapshots if getattr(s, metric) is not None]
        if len(values) < 10:
            return
        mean = np.mean(values)
        std = np.std(values)
        ucl = mean + n_sigma * std
        lcl = max(0, mean - n_sigma * std)
        self._control_limits[metric] = (ucl, lcl)

    def detect_anomaly(self, snapshot: PerformanceSnapshot) -> List[Tuple[str, float, float, float]]:
        anomalies = []
        for metric in ["accuracy", "latency_ms", "error_rate"]:
            val = getattr(snapshot, metric)
            if val is None or metric not in self._control_limits:
                continue
            ucl, lcl = self._control_limits[metric]
            if val > ucl or val < lcl:
                anomalies.append((metric, val, lcl, ucl))
        return anomalies

# --------------------------------------------------------------------
# Drift Monitor Orchestrator
# --------------------------------------------------------------------
class ModelMonitor:
    def __init__(self, config_path="config/monitoring/config.json"):
        self.config = self._load_config(config_path)
        self.reference_stats: Dict[str, Dict] = {}
        self.drift_reports: List[DriftReport] = []
        self.performance_monitor = PerformanceMonitor()
        self._alert_callbacks = []

    def _load_config(self, path):
        default = {
            "data_drift": {
                "method": "psi",
                "psi_threshold_moderate": 0.1,
                "psi_threshold_significant": 0.2,
                "ks_threshold": 0.05,
                "window_size": 10000
            },
            "concept_drift": {
                "method": "adwin",
                "adwin_delta": 0.002,
                "check_interval": 100
            },
            "performance": {
                "control_sigma": 3.0,
                "min_samples": 10,
                "alert_on_accuracy_drop": 0.05
            },
            "alerting": {
                "webhook_url": "",
                "slack_webhook": "",
                "email": ""
            }
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def set_reference(self, model_id: str, version_id: str, reference_data: np.ndarray, feature_names: List[str]):
        ref_stats = {}
        for i, col in enumerate(feature_names):
            col_data = reference_data[:, i]
            ref_stats[col] = {
                "mean": float(np.mean(col_data)),
                "std": float(np.std(col_data)),
                "quantiles": np.percentile(col_data, [0, 25, 50, 75, 100]).tolist(),
                "histogram": np.histogram(col_data, bins=20)[0].tolist()
            }
        self.reference_stats[f"{model_id}_{version_id}"] = ref_stats
        logger.info(f"Reference distribution stored for {model_id} v{version_id}")

    def check_data_drift(self, model_id: str, version_id: str, current_data: np.ndarray, feature_names: List[str]) -> List[DriftReport]:
        reports = []
        ref = self.reference_stats.get(f"{model_id}_{version_id}")
        if not ref:
            raise ValueError("Reference distribution not set")
        method = self.config["data_drift"]["method"]
        for i, col in enumerate(feature_names):
            cur_col = current_data[:, i]
            ref_col_vals = np.random.normal(ref[col]["mean"], ref[col]["std"], len(cur_col))
            if method == "ks":
                from scipy import stats
                stat, p = stats.ks_2samp(ref_col_vals, cur_col)
                threshold = self.config["data_drift"]["ks_threshold"]
                if stat > threshold:
                    severity = AlertSeverity.WARNING if stat < threshold*2 else AlertSeverity.CRITICAL
                    reports.append(DriftReport(
                        report_id=hashlib.md5(f"{model_id}_{col}_{time.time()}".encode()).hexdigest()[:16],
                        model_id=model_id,
                        version_id=version_id,
                        drift_type=DriftType.DATA_DRIFT,
                        feature_name=col,
                        statistic="ks_stat",
                        value=float(stat),
                        threshold=threshold,
                        severity=severity,
                        timestamp=int(time.time()),
                        sample_size=len(cur_col)
                    ))
            elif method == "psi":
                psi = PSIDriftDetector.compute(ref_col_vals, cur_col)
                moderate = self.config["data_drift"]["psi_threshold_moderate"]
                significant = self.config["data_drift"]["psi_threshold_significant"]
                if psi > significant:
                    severity = AlertSeverity.CRITICAL
                elif psi > moderate:
                    severity = AlertSeverity.WARNING
                else:
                    continue
                reports.append(DriftReport(
                    report_id=hashlib.md5(f"{model_id}_{col}_{time.time()}".encode()).hexdigest()[:16],
                    model_id=model_id,
                    version_id=version_id,
                    drift_type=DriftType.DATA_DRIFT,
                    feature_name=col,
                    statistic="psi",
                    value=float(psi),
                    threshold=moderate,
                    severity=severity,
                    timestamp=int(time.time()),
                    sample_size=len(cur_col)
                ))
        return reports

    def check_concept_drift(self, model_id: str, version_id: str, predictions: List[float], ground_truth: List[float]) -> List[DriftReport]:
        errors = [abs(p - g) for p, g in zip(predictions, ground_truth)]
        adwin = ADWIN(delta=self.config["concept_drift"]["adwin_delta"])
        for err in errors:
            adwin.add_element(err)
        if adwin.drift_detected():
            return [DriftReport(
                report_id=hashlib.md5(f"{model_id}_concept_{time.time()}".encode()).hexdigest()[:16],
                model_id=model_id,
                version_id=version_id,
                drift_type=DriftType.CONCEPT_DRIFT,
                feature_name=None,
                statistic="error_mean",
                value=float(np.mean(errors)),
                threshold=0.0,
                severity=AlertSeverity.WARNING,
                timestamp=int(time.time()),
                sample_size=len(errors)
            )]
        return []

    def record_performance(self, snapshot: PerformanceSnapshot):
        self.performance_monitor.add_snapshot(snapshot)
        self.performance_monitor.compute_control_limits("accuracy", self.config["performance"]["control_sigma"])
        self.performance_monitor.compute_control_limits("latency_ms", self.config["performance"]["control_sigma"])
        self.performance_monitor.compute_control_limits("error_rate", self.config["performance"]["control_sigma"])
        anomalies = self.performance_monitor.detect_anomaly(snapshot)
        reports = []
        for metric, val, lcl, ucl in anomalies:
            reports.append(DriftReport(
                report_id=hashlib.md5(f"{snapshot.model_id}_perf_{metric}_{time.time()}".encode()).hexdigest()[:16],
                model_id=snapshot.model_id,
                version_id=snapshot.version_id,
                drift_type=DriftType.PERFORMANCE_DRIFT,
                feature_name=metric,
                statistic="value",
                value=val,
                threshold=ucl,
                severity=AlertSeverity.CRITICAL if metric == "error_rate" and val > ucl else AlertSeverity.WARNING,
                timestamp=int(time.time()),
                sample_size=1
            ))
        return reports

    def get_alerts(self, model_id: str = None, severity: str = None, limit: int = 100) -> List[DriftReport]:
        filtered = self.drift_reports
        if model_id:
            filtered = [r for r in filtered if r.model_id == model_id]
        if severity:
            filtered = [r for r in filtered if r.severity.value == severity]
        return filtered[-limit:]

    def _send_alert(self, report: DriftReport):
        try:
            import requests
            requests.post("http://localhost:8080/v1/notifications/alert", json={
                "title": f"Model Drift Detected: {report.drift_type.value}",
                "message": f"Model {report.model_id} version {report.version_id} – {report.feature_name or report.statistic} = {report.value:.4f} (threshold {report.threshold:.4f})",
                "severity": report.severity.value,
                "source": "model_monitor"
            }, timeout=2)
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

_monitor = None
def get_monitor():
    global _monitor
    if _monitor is None:
        _monitor = ModelMonitor()
    return _monitor
