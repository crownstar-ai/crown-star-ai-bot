# anomaly/monitoring_daemon.py – Background metric collection and anomaly detection
import time
import threading
import requests
import json
import os
from datetime import datetime
from .detector import get_anomaly_detector
from .remediation.orchestrator import get_healing_orchestrator

class MonitoringDaemon:
    def __init__(self, prometheus_url: str = "http://localhost:9090", interval_seconds: int = 30):
        self.prometheus_url = prometheus_url
        self.interval = interval_seconds
        self.running = False
        self.thread = None
        self.detector = get_anomaly_detector()
        self.healer = get_healing_orchestrator()
    
    def _query_prometheus(self, query: str) -> float:
        try:
            resp = requests.get(f"{self.prometheus_url}/api/v1/query", params={"query": query}, timeout=10)
            data = resp.json()
            if data["status"] == "success" and data["data"]["result"]:
                return float(data["data"]["result"][0]["value"][1])
        except:
            pass
        return 0.0
    
    def _collect_metrics(self):
        """Pull metrics from Prometheus and feed to detector"""
        metric_queries = {
            "cpu_usage": 'avg(rate(container_cpu_usage_seconds_total{container="crownstar-api"}[2m]))',
            "memory_usage": 'avg(container_memory_working_set_bytes{container="crownstar-api"}) / 1024 / 1024 / 1024',
            "request_latency_p99": 'histogram_quantile(0.99, rate(crownstar_request_duration_seconds_bucket[5m]))',
            "error_rate": 'rate(crownstar_requests_total{status=~"5.."}[5m]) / rate(crownstar_requests_total[5m])',
            "queue_depth": 'crownstar_queue_depth',
            "cache_hit_rate": 'rate(crownstar_cache_hits_total[5m]) / (rate(crownstar_cache_hits_total[5m]) + rate(crownstar_cache_misses_total[5m]))'
        }
        for metric, query in metric_queries.items():
            value = self._query_prometheus(query)
            self.detector.add_metric(metric, value)
            anomaly = self.detector.detect(metric, value)
            if anomaly["is_anomaly"]:
                print(f"⚠️ Anomaly detected: {metric}={value} – methods: {[m['method'] for m in anomaly['methods']]}")
                self.healer.handle_anomaly(anomaly)
    
    def _run(self):
        while self.running:
            try:
                self._collect_metrics()
            except Exception as e:
                print(f"Monitoring error: {e}")
            time.sleep(self.interval)
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("Anomaly monitoring daemon started")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

# Global instance
_monitor = None
def get_monitoring_daemon():
    global _monitor
    if _monitor is None:
        _monitor = MonitoringDaemon()
    return _monitor
