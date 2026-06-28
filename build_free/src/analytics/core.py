# analytics/core.py – CrownStar Real-Time Analytics & Anomaly Detection Engine
import os, json, time, threading, queue, numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import deque
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("scikit-learn not installed. ML-based anomaly detection disabled.")

@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: int
    labels: Dict[str, str]

@dataclass
class Anomaly:
    id: str
    metric_name: str
    value: float
    expected_range: Tuple[float, float]
    severity: str   # low, medium, high, critical
    timestamp: int
    detection_method: str
    details: Dict

class MetricsCollector:
    """Collects real-time metrics from CrownStar subsystems."""
    def __init__(self, buffer_size: int = 10000):
        self.buffer = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._callbacks = []

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        logger.info("Metrics collector started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def _collect_loop(self):
        while self._running:
            try:
                # Collect system metrics
                self._collect_system_metrics()
                # Collect CrownStar-specific metrics
                self._collect_crownstar_metrics()
                time.sleep(1)  # 1 Hz sampling
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")

    def _collect_system_metrics(self):
        import psutil
        now = int(time.time())
        # CPU
        self.record(MetricPoint("system.cpu.percent", psutil.cpu_percent(), now, {}))
        # Memory
        mem = psutil.virtual_memory()
        self.record(MetricPoint("system.memory.used_percent", mem.percent, now, {}))
        self.record(MetricPoint("system.memory.available_mb", mem.available / 1024**2, now, {}))
        # Disk
        disk = psutil.disk_usage('/')
        self.record(MetricPoint("system.disk.used_percent", disk.percent, now, {}))
        # Network (cumulative)
        net = psutil.net_io_counters()
        self.record(MetricPoint("system.network.bytes_sent", net.bytes_sent, now, {}))
        self.record(MetricPoint("system.network.bytes_recv", net.bytes_recv, now, {}))

    def _collect_crownstar_metrics(self):
        now = int(time.time())
        # In production, these would be read from CrownStarCore
        # For now, placeholder values
        self.record(MetricPoint("crownstar.requests_per_minute", 120 + np.random.normal(0, 10), now, {"tier": "enterprise"}))
        self.record(MetricPoint("crownstar.latency_ms", 45 + np.random.normal(0, 5), now, {}))
        self.record(MetricPoint("crownstar.error_rate", 0.01 + np.random.random()*0.02, now, {}))
        self.record(MetricPoint("crownstar.token_usage", 5000 + np.random.normal(0, 500), now, {}))
        self.record(MetricPoint("crownstar.active_sessions", 23 + np.random.randint(-3, 3), now, {}))

    def record(self, point: MetricPoint):
        with self._lock:
            self.buffer.append(point)
        for cb in self._callbacks:
            try:
                cb(point)
            except Exception as e:
                logger.debug(f"Callback error: {e}")

    def get_recent(self, metric_name: str, seconds: int = 60) -> List[MetricPoint]:
        cutoff = int(time.time()) - seconds
        with self._lock:
            return [p for p in self.buffer if p.name == metric_name and p.timestamp >= cutoff]

class AnomalyDetector:
    """Detects anomalies using statistical and ML methods."""
    def __init__(self, config: Dict = None):
        self.config = config or {
            "zscore_threshold": 3.0,
            "iqr_multiplier": 1.5,
            "window_seconds": 300,
            "min_samples": 30,
            "isolation_forest_contamination": 0.05
        }
        self._historical: Dict[str, deque] = {}
        self._isolation_forest = None
        if HAS_SKLEARN:
            self._isolation_forest = IsolationForest(contamination=self.config["isolation_forest_contamination"], random_state=42)

    def detect(self, metric: MetricPoint, history: List[MetricPoint]) -> Optional[Anomaly]:
        """Detect anomaly in a single metric point given its history."""
        if len(history) < self.config["min_samples"]:
            return None
        values = [p.value for p in history]
        # Z‑score method
        mean = np.mean(values)
        std = np.std(values)
        if std > 0:
            zscore = abs(metric.value - mean) / std
            if zscore > self.config["zscore_threshold"]:
                return Anomaly(
                    id=f"{metric.name}_{metric.timestamp}",
                    metric_name=metric.name,
                    value=metric.value,
                    expected_range=(mean - self.config["zscore_threshold"]*std, mean + self.config["zscore_threshold"]*std),
                    severity="high" if zscore > 5 else "medium",
                    timestamp=metric.timestamp,
                    detection_method="zscore",
                    details={"zscore": zscore, "mean": mean, "std": std}
                )
        # IQR method (robust)
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        lower = q1 - self.config["iqr_multiplier"] * iqr
        upper = q3 + self.config["iqr_multiplier"] * iqr
        if metric.value < lower or metric.value > upper:
            return Anomaly(
                id=f"{metric.name}_{metric.timestamp}_iqr",
                metric_name=metric.name,
                value=metric.value,
                expected_range=(lower, upper),
                severity="medium",
                timestamp=metric.timestamp,
                detection_method="iqr",
                details={"q1": q1, "q3": q3, "iqr": iqr}
            )
        return None

    def update_history(self, metric: MetricPoint):
        if metric.name not in self._historical:
            self._historical[metric.name] = deque(maxlen=10000)
        self._historical[metric.name].append(metric)

class RealTimeMonitor:
    """Main real‑time monitor – streams metrics and anomalies to WebSocket clients."""
    def __init__(self):
        self.collector = MetricsCollector()
        self.detector = AnomalyDetector()
        self._anomaly_queue = queue.Queue()
        self._websocket_clients = []
        self._running = False

    def start(self):
        self.collector.start()
        self._running = True
        # Start anomaly detection worker
        threading.Thread(target=self._detection_loop, daemon=True).start()
        # Start streaming loop for WebSocket
        threading.Thread(target=self._streaming_loop, daemon=True).start()
        logger.info("Real-Time Monitor started")

    def stop(self):
        self._running = False
        self.collector.stop()

    def _detection_loop(self):
        while self._running:
            # Get recent metrics from collector buffer
            # For each unique metric, run detection
            metric_names = set(p.name for p in self.collector.buffer)
            for name in metric_names:
                points = self.collector.get_recent(name, seconds=self.detector.config["window_seconds"])
                for p in points[-10:]:  # check latest points
                    anomaly = self.detector.detect(p, points[:-1])
                    if anomaly:
                        self._anomaly_queue.put(anomaly)
                        # Send to notification system (Paste 64)
                        self._send_alert(anomaly)
                        self.detector.update_history(p)
            time.sleep(2)

    def _streaming_loop(self):
        """Stream metrics and anomalies to WebSocket clients."""
        while self._running:
            # Get latest metrics snapshot
            snapshot = self._get_snapshot()
            # Send to all connected WebSocket clients
            for client in self._websocket_clients:
                try:
                    client.send(json.dumps(snapshot))
                except:
                    self._websocket_clients.remove(client)
            time.sleep(1)

    def _get_snapshot(self) -> Dict:
        now = int(time.time())
        metrics = {}
        for point in list(self.collector.buffer)[-50:]:
            if point.name not in metrics:
                metrics[point.name] = []
            metrics[point.name].append({"value": point.value, "timestamp": point.timestamp})
        # Get recent anomalies
        anomalies = []
        while not self._anomaly_queue.empty():
            anomalies.append(self._anomaly_queue.get())
        return {
            "timestamp": now,
            "metrics": metrics,
            "anomalies": [asdict(a) for a in anomalies[-10:]],
            "healthy": len(anomalies) == 0
        }

    def _send_alert(self, anomaly: Anomaly):
        """Send alert via existing notification system (Paste 64)."""
        try:
            import requests
            requests.post("http://localhost:8080/v1/notifications/alert", json={
                "title": f"Anomaly Detected: {anomaly.metric_name}",
                "message": f"Value {anomaly.value:.2f} outside expected range {anomaly.expected_range}. Severity: {anomaly.severity}",
                "severity": anomaly.severity,
                "source": "analytics_engine"
            }, timeout=2)
        except:
            pass

    def register_websocket_client(self, client):
        self._websocket_clients.append(client)

    def unregister_websocket_client(self, client):
        if client in self._websocket_clients:
            self._websocket_clients.remove(client)

_monitor = None
def get_monitor():
    global _monitor
    if _monitor is None:
        _monitor = RealTimeMonitor()
        _monitor.start()
    return _monitor
