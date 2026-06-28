# caching/cache_service.py – Multi‑level cache (L1: LRU, L2: Redis)
import time
import json
import hashlib
from typing import Optional, Any, Dict
from collections import OrderedDict
import redis
import os

class LRUCache:
    """In‑memory LRU cache (L1)"""
    def __init__(self, capacity: int = 1000, ttl_seconds: int = 300):
        self.capacity = capacity
        self.ttl = ttl_seconds
        self._cache = OrderedDict()
        self._expiry = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        if self._expiry.get(key, 0) < time.time():
            self.delete(key)
            return None
        self._cache.move_to_end(key)
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        self._expiry[key] = time.time() + self.ttl
        if len(self._cache) > self.capacity:
            oldest = next(iter(self._cache))
            self.delete(oldest)
    
    def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]
            del self._expiry[key]
    
    def clear(self):
        self._cache.clear()
        self._expiry.clear()
    
    def size(self) -> int:
        return len(self._cache)

class RedisCache:
    """Redis cache (L2)"""
    def __init__(self, redis_url: str = None, default_ttl: int = 3600):
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.default_ttl = default_ttl
        self._client = None
        self._connect()
    
    def _connect(self):
        try:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            self._client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self._client = None
    
    def get(self, key: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            return self._client.get(key)
        except:
            return None
    
    def set(self, key: str, value: str, ttl: int = None):
        if not self._client:
            return
        ttl = ttl or self.default_ttl
        try:
            self._client.setex(key, ttl, value)
        except:
            pass
    
    def delete(self, key: str):
        if not self._client:
            return
        try:
            self._client.delete(key)
        except:
            pass
    
    def delete_pattern(self, pattern: str):
        if not self._client:
            return
        try:
            keys = self._client.keys(pattern)
            if keys:
                self._client.delete(*keys)
        except:
            pass
    
    def clear(self):
        if not self._client:
            return
        try:
            self._client.flushdb()
        except:
            pass

class CacheService:
    """Multi‑level cache facade (L1 = LRU, L2 = Redis)"""
    def __init__(self, l1_capacity: int = 1000, l1_ttl: int = 300, l2_ttl: int = 3600):
        self.l1 = LRUCache(capacity=l1_capacity, ttl_seconds=l1_ttl)
        self.l2 = RedisCache(default_ttl=l2_ttl)
        self.stats = {"hits": 0, "misses": 0, "l1_hits": 0, "l2_hits": 0}
    
    def _make_key(self, prefix: str, *args) -> str:
        """Generate deterministic cache key"""
        key_str = f"{prefix}:{':'.join(str(a) for a in args)}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    def get(self, prefix: str, *args) -> Optional[str]:
        key = self._make_key(prefix, *args)
        # L1
        val = self.l1.get(key)
        if val is not None:
            self.stats["hits"] += 1
            self.stats["l1_hits"] += 1
            return val
        # L2
        val = self.l2.get(key)
        if val is not None:
            self.l1.set(key, val)
            self.stats["hits"] += 1
            self.stats["l2_hits"] += 1
            return val
        self.stats["misses"] += 1
        return None
    
    def set(self, prefix: str, value: str, *args, ttl: int = None):
        key = self._make_key(prefix, *args)
        self.l1.set(key, value)
        self.l2.set(key, value, ttl)
    
    def invalidate(self, prefix: str, *args):
        key = self._make_key(prefix, *args)
        self.l1.delete(key)
        self.l2.delete(key)
    
    def invalidate_pattern(self, pattern: str):
        self.l2.delete_pattern(f"*{pattern}*")
        # L1 can't pattern‑delete easily, so clear whole L1 if pattern broad
        if len(pattern) < 5:
            self.l1.clear()
        else:
            # For simplicity in demo, clear L1 on any pattern invalidation
            self.l1.clear()
    
    def clear(self):
        self.l1.clear()
        self.l2.clear()
        self.stats = {"hits": 0, "misses": 0, "l1_hits": 0, "l2_hits": 0}
    
    def get_stats(self) -> Dict:
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "l1_hits": self.stats["l1_hits"],
            "l2_hits": self.stats["l2_hits"],
            "hit_rate": hit_rate,
            "l1_size": self.l1.size()
        }

# Global instance
_cache = None
def get_cache():
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache
