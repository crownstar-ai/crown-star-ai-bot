# sharding/routing/router.py – Routes database operations to shards
import threading
from typing import Dict, Any, List, Optional, Callable
from ..pool.connection_pool import get_shard_manager
from ..strategies.strategies import get_strategy

class ShardRouter:
    def __init__(self, config_path: str = "config/sharding/sharding_config.json"):
        self.config = self._load_config(config_path)
        self.strategy = get_strategy(self.config["strategy"], self.config.get("strategy_config"))
        self.shard_manager = get_shard_manager()
        self._local = threading.local()
    
    def _load_config(self, path):
        import json, os
        default = {
            "strategy": "consistent_hash",
            "strategy_config": {"virtual_nodes": 150},
            "total_shards": 4,
            "shard_key": "user_id",
            "shard_map": {0: "shard_0", 1: "shard_1", 2: "shard_2", 3: "shard_3"}
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def set_shard_context(self, shard_key: str):
        self._local.shard_key = shard_key
        self._local.shard_id = self.strategy.get_shard(shard_key, self.config["total_shards"], self.config["shard_map"])
    
    def get_shard_id(self, shard_key: str = None) -> str:
        key = shard_key or getattr(self._local, "shard_key", None)
        if not key:
            raise ValueError("Shard key not set in context")
        return self.strategy.get_shard(key, self.config["total_shards"], self.config["shard_map"])
    
    def get_connection(self, shard_key: str = None, use_replica: bool = False):
        shard_id = self.get_shard_id(shard_key)
        pool = self.shard_manager.get_shard_pool(shard_id, use_replica)
        if not pool:
            raise RuntimeError(f"No pool for shard {shard_id}")
        return pool.get_connection()
    
    def execute_on_shard(self, shard_key: str, sql: str, params: tuple = None, use_replica: bool = False) -> Any:
        with self.get_connection(shard_key, use_replica) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            if sql.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
            conn.commit()
            return cursor.lastrowid
    
    def execute_batch(self, shard_key: str, queries: List[tuple]) -> bool:
        with self.get_connection(shard_key) as conn:
            cursor = conn.cursor()
            for sql, params in queries:
                cursor.execute(sql, params)
            conn.commit()
        return True

_shard_router = None
def get_shard_router():
    global _shard_router
    if _shard_router is None:
        _shard_router = ShardRouter()
    return _shard_router
