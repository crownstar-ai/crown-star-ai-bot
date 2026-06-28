# crownstar_enterprise_api.py – Enterprise API server with rate limiting, load balancing, metrics
import asyncio
import json
import time
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client import make_asgi_app
import uvicorn
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core
from enterprise.rate_limiter import RedisRateLimiter, RateLimitMiddleware
from enterprise.load_balancer import ConsistentHashLoadBalancer, ClusterNode
from enterprise.cluster_registry import ClusterRegistry, ServiceNode

# Initialize core (single node mode, or distributed via load balancer)
core = create_core()

# Enterprise configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
NODE_ID = os.environ.get("NODE_ID", f"node-{os.getpid()}")
SERVICE_TYPE = "api"

# Initialize Redis and cluster components
rate_limiter = RedisRateLimiter(redis_url=REDIS_URL, default_limit=5000, window_seconds=3600)
cluster_registry = ClusterRegistry(redis_url=REDIS_URL)
load_balancer = ConsistentHashLoadBalancer()

# Register this node
current_node = ServiceNode(
    node_id=NODE_ID,
    host=os.environ.get("NODE_HOST", "localhost"),
    port=int(os.environ.get("API_PORT", 8080)),
    service_type=SERVICE_TYPE,
    tags=json.loads(os.environ.get("NODE_TAGS", "[]")),
    version="7.0.1",
    last_seen=time.time()
)
cluster_registry.start_heartbeat(current_node)

# FastAPI app
app = FastAPI(
    title="CrownStar Enterprise API",
    description="Distributed API with rate limiting, load balancing, and metrics",
    version="7.0.1"
)

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Custom metrics
REQUESTS = Counter('crownstar_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
LATENCY = Histogram('crownstar_request_duration_seconds', 'Request latency', ['endpoint'])
ACTIVE_NODES = Gauge('crownstar_active_nodes', 'Number of active nodes in cluster')

@app.on_event("startup")
async def startup_event():
    # Discover other nodes and update load balancer
    await update_node_registry()

@app.on_event("shutdown")
async def shutdown_event():
    cluster_registry.unregister_node(SERVICE_TYPE, NODE_ID)
    core.vector_memory.close()

async def update_node_registry():
    nodes = cluster_registry.get_nodes(service_type="api")
    ACTIVE_NODES.set(len(nodes))
    for node_info in nodes:
        node = ClusterNode(
            node_id=node_info.node_id,
            host=node_info.host,
            port=node_info.port,
            weight=1,
            healthy=True
        )
        load_balancer.add_node(node)

@app.middleware("http")
async def add_metrics(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    LATENCY.labels(endpoint=request.url.path).observe(duration)
    REQUESTS.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
    return response

# Health and readiness endpoints
@app.get("/v1/health")
async def health():
    return {"status": "healthy", "node": NODE_ID, "timestamp": time.time()}

@app.get("/v1/ready")
async def ready():
    # Check if core is ready
    return {"status": "ready", "node": NODE_ID, "core": core is not None}

@app.get("/v1/live")
async def live():
    return {"status": "alive", "node": NODE_ID}

# Cluster status
@app.get("/v1/cluster/nodes")
async def get_cluster_nodes():
    nodes = cluster_registry.get_nodes()
    return {"nodes": [{"id": n.node_id, "host": n.host, "port": n.port, "service_type": n.service_type, "version": n.version} for n in nodes], "total": len(nodes)}

@app.get("/v1/cluster/status")
async def cluster_status():
    stats = load_balancer.get_stats()
    return stats

# Chat endpoint with rate limiting (already applied by middleware)
@app.post("/v1/chat")
async def chat(request: Request):
    data = await request.json()
    query = data.get("query", "")
    modules = data.get("modules", {})
    tier = data.get("tier", None)
    model = data.get("model", None)
    
    if tier:
        core.set_tier(tier)
    for mod, enabled in modules.items():
        core.set_module(mod, enabled)
    if model:
        core.set_model(model)
    
    result = core.answer(query)
    return {
        "answer": result["answer"],
        "node": NODE_ID,
        "modules_active": result["modules_active"],
        "conversation_id": result["conversation_id"],
        "latency_ms": result["latency_ms"],
        "tier": core.tier
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8080)), log_level="info")
