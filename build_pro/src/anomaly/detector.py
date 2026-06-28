# anomaly/detector.py – Anomaly detection engine
import numpy as np
import time
import json
import os
from collections import deque
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import threading
import requests

class StatisticalAnomalyDetector:
    """Z‑score, IQR, and moving average anomaly detection"""
    def __init__(self, window_size: int = 60, threshold_zscore: float = 3.0, threshold_iqr: float = 1.5):
        self.window_size = window_size
        self.threshold_zscore = threshold_zscore
        self.threshold_iqr = threshold_iqr
        self.history = deque(maxlen=window_size)
    
    def add_value(self, value: float):
        self.history.append(value)
    
    def detect_zscore(self, value: float) -> Tuple[bool, float]:
        if len(self.history) < 10:
            return False, 0.0
        mean = np.mean(self.history)
        std = np.std(self.history)
        if std == 0:
            return False, 0.0
        z = (value - mean) / std
        is_anomaly = abs(z) > self.threshold_zscore
        return is_anomaly, z
    
    def detect_iqr(self, value: float) -> Tuple[bool, float]:
        if len(self.history) < 10:
            return False, 0.0
        q1 = np.percentile(self.history, 25)
        q3 = np.percentile(self.history, 75)
        iqr = q3 - q1
        lower = q1 - self.threshold_iqr * iqr
        upper = q3 + self.threshold_iqr * iqr
        is_anomaly = value < lower or value > upper
        deviation = max(0, (value - upper) / (upper+1e-9) if value > upper else (lower - value) / (lower+1e-9) if value < lower else 0)
        return is_anomaly, deviation
    
    def detect_moving_average(self, value: float, window_smooth: int = 5) -> Tuple[bool, float]:
        if len(self.history) < window_smooth:
            return False, 0.0
        recent = list(self.history)[-window_smooth:]
        ma = np.mean(recent)
        diff_pct = abs(value - ma) / (ma + 1e-9)
        is_anomaly = diff_pct > 0.5  # 50% deviation
        return is_anomaly, diff_pct

class MLAnomalyDetector:
    """Isolation Forest (optional) – lazy load sklearn"""
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.model = None
        self._fitted = False
    
    def _init_model(self):
        try:
            from sklearn.ensemble import IsolationForest
            self.model = IsolationForest(contamination=self.contamination, random_state=42)
        except ImportError:
            print("scikit-learn not installed – ML anomaly detection disabled")
            self.model = None
    
    def fit(self, data: List[float]):
        if self.model is None:
            self._init_model()
        if self.model and len(data) > 20:
            X = np.array(data).reshape(-1, 1)
            self.model.fit(X)
            self._fitted = True
    
    def predict(self, value: float) -> Tuple[bool, float]:
        if not self._fitted or self.model is None:
            return False, 0.0
        X = np.array([[value]])
        pred = self.model.predict(X)[0]
        score = self.model.score_samples(X)[0]
        is_anomaly = pred == -1
        # Score is negative; larger magnitude = more anomalous
        return is_anomaly, -score

class AnomalyDetector:
    def __init__(self, config_path: str = "config/anomaly/config.json"):
        self.config = self._load_config(config_path)
        self.stat_detector = StatisticalAnomalyDetector(
            window_size=self.config.get("stat_window", 60),
            threshold_zscore=self.config.get("zscore_threshold", 3.0),
            threshold_iqr=self.config.get("iqr_threshold", 1.5)
        )
        self.ml_detector = MLAnomalyDetector(contamination=self.config.get("ml_contamination", 0.1))
        self.metrics_buffer = {}  # metric_name -> deque
        self.anomaly_history = []  # list of dict
        self._init_buffers()
    
    def _load_config(self, path):
        default = {
            "stat_window": 60,
            "zscore_threshold": 3.0,
            "iqr_threshold": 1.5,
            "ml_enabled": False,
            "ml_contamination": 0.1,
            "detection_interval_seconds": 30,
            "metrics": ["cpu_usage", "memory_usage", "request_latency_p99", "error_rate", "queue_depth"]
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {**default, **json.load(f)}
        return default
    
    def _init_buffers(self):
        for metric in self.config["metrics"]:
            self.metrics_buffer[metric] = deque(maxlen=self.config["stat_window"])
    
    def add_metric(self, metric_name: str, value: float):
        if metric_name not in self.metrics_buffer:
            return
        self.metrics_buffer[metric_name].append(value)
        self.stat_detector.history = self.metrics_buffer[metric_name]  # share reference
    
    def detect(self, metric_name: str, value: float) -> Dict:
        """Run anomaly detection on a single metric value"""
        result = {
            "metric": metric_name,
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            "is_anomaly": False,
            "methods": [],
            "score": 0.0
        }
        if metric_name not in self.metrics_buffer:
            return result
        
        # Statistical methods
        is_z, zscore = self.stat_detector.detect_zscore(value)
        is_iqr, iqr_dev = self.stat_detector.detect_iqr(value)
        is_ma, ma_pct = self.stat_detector.detect_moving_average(value)
        
        if is_z:
            result["methods"].append({"method": "zscore", "score": zscore})
        if is_iqr:
            result["methods"].append({"method": "iqr", "score": iqr_dev})
        if is_ma:
            result["methods"].append({"method": "moving_average", "score": ma_pct})
        
        # ML method (if enabled and fitted)
        if self.config.get("ml_enabled", False):
            # Need to have fitted model on historical data
            if len(self.metrics_buffer[metric_name]) > 20:
                self.ml_detector.fit(list(self.metrics_buffer[metric_name]))
            is_ml, ml_score = self.ml_detector.predict(value)
            if is_ml:
                result["methods"].append({"method": "isolation_forest", "score": ml_score})
        
        result["is_anomaly"] = len(result["methods"]) > 0
        result["score"] = max([m["score"] for m in result["methods"]], default=0.0)
        
        if result["is_anomaly"]:
            self.anomaly_history.append(result)
            # Trim history
            if len(self.anomaly_history) > 1000:
                self.anomaly_history = self.anomaly_history[-500:]
        
        return result

# Global instance
_anomaly_detector = None
def get_anomaly_detector():
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector
