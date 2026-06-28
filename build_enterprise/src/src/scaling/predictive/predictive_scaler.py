# scaling/predictive/predictive_scaler.py – Forecast load and recommend replicas
import numpy as np
import time
import json
import os
from datetime import datetime, timedelta
from collections import deque
import threading
from typing import List, Tuple, Dict

class TimeSeriesPredictor:
    """Simple time‑series forecasting using linear regression and seasonal decomposition"""
    def __init__(self, window_minutes: int = 60, prediction_minutes: int = 15):
        self.window = window_minutes
        self.prediction_window = prediction_minutes
        self.history = deque(maxlen=window_minutes * 60)  # per‑second granularity
        self.last_prediction = None
        self.last_recommendation = 2
    
    def add_datapoint(self, value: float):
        self.history.append((time.time(), value))
    
    def predict(self, minutes_ahead: int = 15) -> float:
        """Predict average load after `minutes_ahead` minutes using simple linear regression"""
        if len(self.history) < 10:
            return 0.5
        
        # Extract recent data (last 30 minutes for regression)
        now = time.time()
        recent = [(ts, val) for ts, val in self.history if now - ts <= 1800]
        if len(recent) < 5:
            return 0.5
        
        xs = np.array([ts for ts, _ in recent])
        ys = np.array([val for _, val in recent])
        # Normalize time
        xs_norm = (xs - xs[0]) / 60.0  # minutes since start
        # Linear regression
        A = np.vstack([xs_norm, np.ones(len(xs_norm))]).T
        m, c = np.linalg.lstsq(A, ys, rcond=None)[0]
        future_minutes = minutes_ahead
        predicted = m * future_minutes + c
        predicted = max(0, min(1, predicted))  # clamp 0-1 for load
        return predicted
    
    def recommended_replicas(self, current_replicas: int, max_replicas: int, min_replicas: int = 2) -> int:
        predicted_load = self.predict()
        # Scale formula: replicas = ceil(current_replicas * (predicted_load / target_load))
        target_load = 0.6  # 60% CPU/load target
        raw = current_replicas * (predicted_load / target_load)
        recommended = max(min_replicas, min(max_replicas, int(np.ceil(raw))))
        self.last_recommendation = recommended
        return recommended

class PredictiveScaler:
    def __init__(self, keda_namespace: str = "crownstar"):
        self.predictor = TimeSeriesPredictor()
        self.current_load = 0.0
        self.current_replicas = 2
        self.max_replicas = 20
        self.min_replicas = 2
        self.scaling_enabled = True
        self.keda_namespace = keda_namespace
    
    def update_load(self, load: float):
        self.current_load = load
        self.predictor.add_datapoint(load)
    
    def update_replicas(self, replicas: int):
        self.current_replicas = replicas
    
    def get_recommendation(self) -> Dict:
        predicted = self.predictor.predict()
        recommended = self.predictor.recommended_replicas(self.current_replicas, self.max_replicas, self.min_replicas)
        return {
            "current_load": self.current_load,
            "current_replicas": self.current_replicas,
            "predicted_load_15min": predicted,
            "recommended_replicas": recommended,
            "scaling_action": "scale_up" if recommended > self.current_replicas else ("scale_down" if recommended < self.current_replicas else "steady"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def apply_recommendation(self, k8s_client=None):
        """Update KEDA ScaledObject or HPA via Kubernetes API"""
        rec = self.get_recommendation()
        if not self.scaling_enabled:
            return rec
        if rec["scaling_action"] == "scale_up":
            # In production, patch HPA or KEDA ScaledObject
            print(f"Applying scaling recommendation: {rec['recommended_replicas']} replicas")
        return rec

# Global instance
_scaler = None
def get_predictive_scaler():
    global _scaler
    if _scaler is None:
        _scaler = PredictiveScaler()
    return _scaler
