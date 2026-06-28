# enterprise/load_balancer.py – Consistent hashing for multi-node clusters
import hashlib
import json
import time
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import OrderedDict

@dataclass
class ClusterNode:
    node_id: str
    host: str
    port: int
    weight: int = 1
    healthy: bool = True
    last_heartbeat: float = 0.0
    tags: List[str] = None

class ConsistentHashLoadBalancer:
    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring = OrderedDict()
        self.nodes: Dict[str, ClusterNode] = {}
        self.heartbeat_timeout = 30  # seconds
    
    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def add_node(self, node: ClusterNode):
        self.nodes[node.node_id] = node
        for i in range(self.virtual_nodes):
            virtual_key = f"{node.node_id}:{i}"
            hash_val = self._hash(virtual_key)
            self.ring[hash_val] = node.node_id
        self._sort_ring()
    
    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            del self.nodes[node_id]
            # Remove virtual nodes
            keys_to_remove = [k for k, v in self.ring.items() if v == node_id]
            for k in keys_to_remove:
                del self.ring[k]
    
    def _sort_ring(self):
        sorted_items = sorted(self.ring.items())
        self.ring.clear()
        for k, v in sorted_items:
            self.ring[k] = v
    
    def get_node(self, key: str) -> Optional[ClusterNode]:
        if not self.ring:
            return None
        hash_val = self._hash(key)
        # Find first node with hash >= key hash
        for ring_hash, node_id in self.ring.items():
            if ring_hash >= hash_val:
                node = self.nodes.get(node_id)
                if node and node.healthy:
                    return node
        # Wrap around
        for ring_hash, node_id in self.ring.items():
            node = self.nodes.get(node_id)
            if node and node.healthy:
                return node
        return None
    
    def update_health(self, node_id: str, healthy: bool):
        if node_id in self.nodes:
            self.nodes[node_id].healthy = healthy
            self.nodes[node_id].last_heartbeat = time.time()
    
    def check_health_all(self):
        for node_id, node in self.nodes.items():
            if time.time() - node.last_heartbeat > self.heartbeat_timeout:
                node.healthy = False
    
    def get_all_healthy(self) -> List[ClusterNode]:
        return [n for n in self.nodes.values() if n.healthy]
    
    def get_stats(self) -> Dict:
        return {
            "total_nodes": len(self.nodes),
            "healthy_nodes": len(self.get_all_healthy()),
            "ring_size": len(self.ring),
            "nodes": [
                {
                    "id": n.node_id,
                    "host": n.host,
                    "port": n.port,
                    "healthy": n.healthy,
                    "weight": n.weight
                } for n in self.nodes.values()
            ]
        }
