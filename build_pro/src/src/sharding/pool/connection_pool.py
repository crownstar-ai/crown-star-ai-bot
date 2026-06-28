# sharding/pool/connection_pool.py – Database connection pools per shard
import sqlite3
import threading
from typing import Dict, Optional, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger("crownstar.sharding.pool")

class ShardConnectionPool:
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = threading.Queue(maxsize=max_connections)
        self._size = 0
        self._lock = threading.Lock()
        for _ in range(max_connections):
            self._pool.put(self._create_connection())
            self._size += 1
    
    def _create_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    @contextmanager
    def get_connection(self):
        conn = self._pool.get()
        try:
            yield conn
        finally:
            self._pool.put(conn)
    
    def close_all(self):
        while not self._pool.empty():
            conn = self._pool.get()
            conn.close()

class PostgresShardPool:
    def __init__(self, connection_string: str, max_connections: int = 10):
        import psycopg2
        from psycopg2 import pool
        self.pool = pool.SimpleConnectionPool(1, max_connections, connection_string)
    
    @contextmanager
    def get_connection(self):
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)
    
    def close_all(self):
        self.pool.closeall()

class MySQLShardPool:
    def __init__(self, host: str, port: int, user: str, password: str, database: str, max_connections: int = 10):
        import mysql.connector
        from mysql.connector import pooling
        config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "pool_name": f"shard_{database}",
            "pool_size": max_connections
        }
        self.pool = mysql.connector.pooling.MySQLConnectionPool(**config)
    
    @contextmanager
    def get_connection(self):
        conn = self.pool.get_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    def close_all(self):
        pass  # pool closes automatically

class ShardManager:
    def __init__(self, config: Dict):
        self.shards = {}
        self.replicas = {}
        self.active_shard = None
        self._init_pools(config)
    
    def _init_pools(self, config):
        for shard_id, shard_cfg in config.get("shards", {}).items():
            db_type = shard_cfg.get("type", "sqlite")
            if db_type == "sqlite":
                self.shards[shard_id] = ShardConnectionPool(shard_cfg["path"], shard_cfg.get("max_connections", 10))
            elif db_type == "postgres":
                self.shards[shard_id] = PostgresShardPool(shard_cfg["connection_string"], shard_cfg.get("max_connections", 10))
            elif db_type == "mysql":
                self.shards[shard_id] = MySQLShardPool(
                    shard_cfg["host"], shard_cfg["port"],
                    shard_cfg["user"], shard_cfg["password"],
                    shard_cfg["database"], shard_cfg.get("max_connections", 10)
                )
            # Initialize replicas
            for replica_cfg in shard_cfg.get("replicas", []):
                if db_type == "sqlite":
                    replica_pool = ShardConnectionPool(replica_cfg["path"], replica_cfg.get("max_connections", 5))
                else:
                    replica_pool = PostgresShardPool(replica_cfg["connection_string"], replica_cfg.get("max_connections", 5))
                self.replicas.setdefault(shard_id, []).append(replica_pool)
    
    def get_shard_pool(self, shard_id: str, use_replica: bool = False) -> Optional[ShardConnectionPool]:
        if use_replica and shard_id in self.replicas and self.replicas[shard_id]:
            # Round-robin or random replica selection
            import random
            return random.choice(self.replicas[shard_id])
        return self.shards.get(shard_id)
    
    def close_all(self):
        for pool in self.shards.values():
            pool.close_all()
        for replica_list in self.replicas.values():
            for pool in replica_list:
                pool.close_all()

_shard_manager = None
def get_shard_manager():
    global _shard_manager
    if _shard_manager is None:
        _shard_manager = ShardManager({})
    return _shard_manager
