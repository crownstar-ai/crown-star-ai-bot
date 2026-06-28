# deploy/health_checker.py – Multi-cloud health checks for failover
import requests, time, threading
from .orchestrator.orchestrator import get_orchestrator

class HealthChecker:
    def __init__(self):
        self.orch = get_orchestrator()
        self.failure_counts = {}

    def check_environment(self, env_id: str) -> bool:
        env = self.orch.environments.get(env_id)
        if not env:
            return False
        # Assume health endpoint
        try:
            # In real, query load balancer or instance IP
            resp = requests.get(f"http://crownstar-{env.name}.local/health", timeout=5)
            return resp.status_code == 200
        except:
            return False

    def start_monitoring(self, interval_seconds=30):
        def monitor():
            while True:
                for env_id, env in self.orch.environments.items():
                    healthy = self.check_environment(env_id)
                    if not healthy:
                        self.failure_counts[env_id] = self.failure_counts.get(env_id, 0) + 1
                        if self.failure_counts[env_id] >= 3:
                            # Trigger failover
                            self._trigger_failover(env_id)
                    else:
                        self.failure_counts[env_id] = 0
                time.sleep(interval_seconds)
        threading.Thread(target=monitor, daemon=True).start()

    def _trigger_failover(self, failed_env_id):
        # Find another environment (same provider diff region, or diff provider)
        candidates = [e for e in self.orch.environments.values() if e.env_id != failed_env_id]
        if candidates:
            target = candidates[0]
            self.orch.failover(failed_env_id, target.env_id)
