# sharding/strategies/strategies.py – Shard key assignment strategies
import hashlib
import bisect
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

class ShardingStrategy(ABC):
    @abstractmethod
    def get_shard(self, key: str, total_shards: int, shard_map: Dict[int, str]) -> str:
        pass
    
    @abstractmethod
    def get_all_shards(self, key: str = None) -> List[str]:
        pass

class ModuloSharding(ShardingStrategy):
    """Simple modulo sharding: shard = hash(key) % total_shards"""
    def get_shard(self, key: str, total_shards: int, shard_map: Dict[int, str]) -> str:
        hash_val = hash(key) & 0xffffffff
        shard_idx = hash_val % total_shards
        return shard_map.get(shard_idx, f"shard_{shard_idx}")
    
    def get_all_shards(self, key: str = None) -> List[str]:
        return [f"shard_{i}" for i in range(10)]  # placeholder

class RangeSharding(ShardingStrategy):
    """Range sharding: key range determines shard"""
    def __init__(self, ranges: Dict[str, List[int]] = None):
        self.ranges = ranges or {
            "shard_0": (0, 100000),
            "shard_1": (100001, 200000),
            "shard_2": (200001, 300000)
        }
    
    def get_shard(self, key: str, total_shards: int, shard_map: Dict[int, str]) -> str:
        # Convert key to numeric (e.g., hash or user_id numeric)
        try:
            numeric = int(key) if key.isdigit() else hash(key) & 0xffffffff
        except:
            numeric = hash(key) & 0xffffffff
        for shard, (low, high) in self.ranges.items():
            if low <= numeric <= high:
                return shard
        return "shard_default"
    
    def get_all_shards(self, key: str = None) -> List[str]:
        return list(self.ranges.keys())

class ConsistentHashSharding(ShardingStrategy):
    """Consistent hashing with virtual nodes"""
    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}  # hash -> shard
        self.sorted_keys = []
    
    def build_ring(self, shards: List[str]):
        self.ring = {}
        for shard in shards:
            for i in range(self.virtual_nodes):
                virtual_key = f"{shard}:{i}"
                hash_val = self._hash(virtual_key)
                self.ring[hash_val] = shard
        self.sorted_keys = sorted(self.ring.keys())
    
    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def get_shard(self, key: str, total_shards: int, shard_map: Dict[int, str]) -> str:
        if not self.ring:
            self.build_ring(list(shard_map.values()))
        hash_val = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_val)
        if idx == len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]
    
    def get_all_shards(self, key: str = None) -> List[str]:
        return list(set(self.ring.values()))

def get_strategy(name: str, config: Dict = None) -> ShardingStrategy:
    if name == "modulo":
        return ModuloSharding()
    elif name == "range":
        return RangeSharding(config.get("ranges") if config else None)
    elif name == "consistent_hash":
        return ConsistentHashSharding(virtual_nodes=config.get("virtual_nodes", 150) if config else 150)
    else:
        return ModuloSharding()
