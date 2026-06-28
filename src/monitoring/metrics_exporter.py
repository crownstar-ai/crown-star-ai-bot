# monitoring/metrics_exporter.py – Custom Prometheus metrics for CrownStar
import time
import psutil
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, REGISTRY
from fastapi import Response
import threading
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core

# Core instance (shared)
core = None

# Define metrics
REQUESTS_TOTAL = Counter('crownstar_requests_total', 'Total requests', ['method', 'endpoint', 'tier', 'status'])
REQUESTS_ACTIVE = Gauge('crownstar_requests_active', 'Active requests')
LATENCY_SECONDS = Histogram('crownstar_request_duration_seconds', 'Request latency', ['endpoint', 'tier'],
                            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
TOKENS_GENERATED = Counter('crownstar_tokens_generated_total', 'Total tokens generated', ['model', 'tier'])
MEMORY_USAGE = Gauge('crownstar_memory_usage_bytes', 'Memory usage in bytes', ['type'])
CPU_USAGE = Gauge('crownstar_cpu_usage_percent', 'CPU usage percentage')
ACTIVE_MODULES = Gauge('crownstar_active_modules', 'Number of active math modules')
MODULE_TOGGLES = Counter('crownstar_module_toggles_total', 'Module toggle events', ['module', 'state'])
CURRENT_TIER = Info('crownstar_tier', 'Current subscription tier')
CURRENT_MODEL = Info('crownstar_model', 'Current language model')
MODEL_USAGE = Counter('crownstar_model_requests_total', 'Requests per model', ['model'])
CLUSTER_NODES = Gauge('crownstar_cluster_nodes', 'Number of active cluster nodes')
HEALTH_STATUS = Gauge('crownstar_health_status', 'Health status (1=healthy, 0=unhealthy)')

def update_system_metrics():
    """Background thread to update system metrics"""
    while True:
        try:
            MEMORY_USAGE.labels(type='rss').set(psutil.Process().memory_info().rss)
            MEMORY_USAGE.labels(type='vms').set(psutil.Process().memory_info().vms)
            CPU_USAGE.set(psutil.cpu_percent(interval=1))
            if core:
                ACTIVE_MODULES.set(len(core.modules.get_active()))
                CURRENT_TIER.info({'tier': core.tier})
                if core.current_model:
                    CURRENT_MODEL.info({'model': core.current_model})
                HEALTH_STATUS.set(1)
            else:
                HEALTH_STATUS.set(0)
        except Exception as e:
            print(f"Metrics update error: {e}")
        time.sleep(5)

def start_metrics_updater():
    thread = threading.Thread(target=update_system_metrics, daemon=True)
    thread.start()

def record_request(method, endpoint, tier, status, duration_seconds):
    REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, tier=tier, status=status).inc()
    LATENCY_SECONDS.labels(endpoint=endpoint, tier=tier).observe(duration_seconds)

def record_tokens(model, tier, token_count):
    TOKENS_GENERATED.labels(model=model, tier=tier).inc(token_count)

def record_module_toggle(module, state):
    MODULE_TOGGLES.labels(module=module, state=str(state)).inc()

def record_model_usage(model):
    MODEL_USAGE.labels(model=model).inc()

def set_active_requests(count):
    REQUESTS_ACTIVE.set(count)

def set_cluster_nodes(count):
    CLUSTER_NODES.set(count)

def get_metrics():
    return generate_latest(REGISTRY)

def register_core(core_instance):
    global core
    core = core_instance
