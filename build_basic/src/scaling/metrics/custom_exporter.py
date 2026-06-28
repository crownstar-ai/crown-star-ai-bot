# scaling/metrics/custom_exporter.py – Export custom metrics for auto‑scaling
from prometheus_client import Gauge, Counter, start_http_server
import time
import threading
import redis
import os

class CustomMetricsExporter:
    def __init__(self, port: int = 8090):
        self.port = port
        self.request_backlog = Gauge('crownstar_request_backlog', 'Number of pending requests in queue')
        self.queue_depth = Gauge('crownstar_queue_depth', 'Depth of async job queue')
        self.predicted_load_15m = Gauge('crownstar_predicted_load_15m', 'Predicted load for next 15 minutes')
        self.active_spot_instances = Gauge('crownstar_active_spot_instances', 'Number of active spot instances')
        self.idle_status = Gauge('crownstar_idle_status', '1 if system idle, 0 otherwise')
        self.cost_savings_dollars = Counter('crownstar_cost_savings_dollars', 'Accumulated cost savings from optimisation')
    
    def start(self):
        start_http_server(self.port)
        print(f"Custom metrics exporter started on port {self.port}")
        self._start_updater()
    
    def _start_updater(self):
        def update_loop():
            while True:
                # Update queue depth from Redis
                try:
                    r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
                    queue_len = r.llen("job_queue")
                    self.queue_depth.set(queue_len)
                except:
                    pass
                # Update idle status from cost optimizer
                from scaling.cost.cost_optimizer import get_cost_optimizer
                idle = get_cost_optimizer().is_idle()
                self.idle_status.set(1 if idle else 0)
                time.sleep(10)
        threading.Thread(target=update_loop, daemon=True).start()

_exporter = None
def get_custom_exporter():
    global _exporter
    if _exporter is None:
        _exporter = CustomMetricsExporter()
    return _exporter
