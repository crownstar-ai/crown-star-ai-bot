# enterprise/cluster_registry.py – Node registration and discovery
import json
import time
import threading
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import redis

@dataclass
class ServiceNode:
    node_id: str
    host: str
    port: int
    service_type: str  # "api", "worker", "router"
    tags: List[str]
    version: str
    last_seen: float

class ClusterRegistry:
    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 60):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl_seconds
        self._stop_heartbeat = threading.Event()
    
    def register_node(self, node: ServiceNode):
        key = f"cluster:nodes:{node.service_type}:{node.node_id}"
        data = asdict(node)
        data["last_seen"] = time.time()
        self.redis_client.hset(key, mapping=data)
        self.redis_client.expire(key, self.ttl)
    
    def unregister_node(self, service_type: str, node_id: str):
        key = f"cluster:nodes:{service_type}:{node_id}"
        self.redis_client.delete(key)
    
    def get_nodes(self, service_type: Optional[str] = None) -> List[ServiceNode]:
        pattern = "cluster:nodes:*"
        if service_type:
            pattern = f"cluster:nodes:{service_type}:*"
        nodes = []
        for key in self.redis_client.scan_iter(match=pattern):
            data = self.redis_client.hgetall(key)
            if data:
                node = ServiceNode(
                    node_id=data.get("node_id", ""),
                    host=data.get("host", ""),
                    port=int(data.get("port", 0)),
                    service_type=data.get("service_type", ""),
                    tags=json.loads(data.get("tags", "[]")),
                    version=data.get("version", ""),
                    last_seen=float(data.get("last_seen", 0))
                )
                if time.time() - node.last_seen < self.ttl:
                    nodes.append(node)
        return nodes
    
    def start_heartbeat(self, node: ServiceNode, interval_seconds: int = 15):
        def heartbeat_loop():
            while not self._stop_heartbeat.is_set():
                self.register_node(node)
                time.sleep(interval_seconds)
        thread = threading.Thread(target=heartbeat_loop, daemon=True)
        thread.start()
        return thread
    
    def stop_heartbeat(self):
        self._stop_heartbeat.set()
