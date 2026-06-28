# feature_store/core.py – CrownStar Real‑Time Feature Store Engine
import os, json, time, hashlib, threading
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import logging
import numpy as np
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class ValueType(Enum):
    INT32 = "int32"; INT64 = "int64"; FLOAT32 = "float32"; FLOAT64 = "float64"
    STRING = "string"; BYTES = "bytes"; VECTOR = "vector"

@dataclass
class EntityDefinition:
    name: str; join_key: str; description: str

@dataclass
class FeatureDefinition:
    name: str; value_type: ValueType; description: str; source: str
    ttl_seconds: Optional[int] = 86400; tags: Dict = field(default_factory=dict)

@dataclass
class FeatureValue:
    feature_name: str; entity_key: str; value: Any; timestamp: int; version: int = 1

@dataclass
class FeatureQuery:
    feature_names: List[str]; entity_keys: List[str]; entity_join_key: str

class FeatureBackend:
    def __init__(self, config: Dict): self.config = config
    def get(self, entity_key: str, feature_name: str) -> Optional[FeatureValue]: raise NotImplementedError
    def get_batch(self, entity_keys: List[str], feature_names: List[str]) -> List[FeatureValue]: raise NotImplementedError
    def put(self, value: FeatureValue) -> bool: raise NotImplementedError
    def put_batch(self, values: List[FeatureValue]) -> int: raise NotImplementedError

class MemoryBackend(FeatureBackend):
    def __init__(self, config):
        super().__init__(config)
        self._store: Dict[str, Dict[str, FeatureValue]] = defaultdict(dict)
    def get(self, entity_key, feature_name): return self._store.get(entity_key, {}).get(feature_name)
    def get_batch(self, entity_keys, feature_names):
        results = []
        for key in entity_keys:
            for fname in feature_names:
                val = self.get(key, fname)
                if val: results.append(val)
        return results
    def put(self, value): self._store[value.entity_key][value.feature_name] = value; return True
    def put_batch(self, values): [self.put(v) for v in values]; return len(values)

class RedisBackend(FeatureBackend):
    def __init__(self, config):
        super().__init__(config); self._client = None
        try:
            import redis
            self._client = redis.Redis(host=config.get("redis_host","localhost"), port=config.get("redis_port",6379), decode_responses=True)
        except ImportError: pass
    def get(self, entity_key, feature_name):
        if not self._client: return None
        data = self._client.get(f"fs:{entity_key}:{feature_name}")
        return FeatureValue(**json.loads(data)) if data else None
    def put(self, value):
        if not self._client: return False
        key = f"fs:{value.entity_key}:{value.feature_name}"
        self._client.setex(key, 86400, json.dumps(asdict(value)))
        return True
    def put_batch(self, values): return sum(1 for v in values if self.put(v))

class OfflineStore:
    def __init__(self, config):
        self.storage_path = config.get("offline_path","data/feature_store/offline")
        os.makedirs(self.storage_path, exist_ok=True)
    def write_feature_log(self, feature_name, entity_key, value, timestamp):
        import pandas as pd
        df = pd.DataFrame([{"feature_name":feature_name,"entity_key":entity_key,"value":value,"timestamp":timestamp}])
        path = os.path.join(self.storage_path, f"{feature_name}.parquet")
        if os.path.exists(path):
            combined = pd.concat([pd.read_parquet(path), df], ignore_index=True)
            combined.to_parquet(path)
        else: df.to_parquet(path)
        return True
    def export_training_data(self, feature_names, start_ts, end_ts):
        import pandas as pd
        merged = None
        for fname in feature_names:
            path = os.path.join(self.storage_path, f"{fname}.parquet")
            if not os.path.exists(path): continue
            df = pd.read_parquet(path)
            df = df[(df["timestamp"]>=start_ts) & (df["timestamp"]<=end_ts)]
            df = df.rename(columns={"value":fname})
            if merged is None: merged = df[["entity_key","timestamp",fname]]
            else: merged = merged.merge(df[["entity_key","timestamp",fname]], on=["entity_key","timestamp"], how="outer")
        return merged if merged is not None else pd.DataFrame()

class FeatureStoreManager:
    def __init__(self, config_path="config/feature_store/config.json"):
        self.config = self._load_config(config_path)
        self.backend = MemoryBackend(self.config) if self.config["backend"]=="memory" else RedisBackend(self.config)
        self.offline = OfflineStore(self.config)
        self.feature_defs = {}; self.entity_defs = {}
        self._load_definitions()
    def _load_config(self, path):
        default = {"backend":"memory","redis_host":"localhost","redis_port":6379,"offline_path":"data/feature_store/offline","online_ttl_seconds":86400,"enable_offline_logging":True}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        return default
    def _load_definitions(self):
        def_path = "config/feature_store/features.json"
        if os.path.exists(def_path):
            with open(def_path,'r') as f:
                data = json.load(f)
                for fname, fdef in data.get("features",{}).items():
                    self.feature_defs[fname] = FeatureDefinition(name=fname, value_type=ValueType(fdef["value_type"]), description=fdef.get("description",""), source=fdef.get("source","batch"), ttl_seconds=fdef.get("ttl_seconds",86400))
                for ename, edef in data.get("entities",{}).items():
                    self.entity_defs[ename] = EntityDefinition(name=ename, join_key=edef["join_key"], description=edef.get("description",""))
    def _save_definitions(self):
        data = {"features":{name:{"value_type":f.value_type.value,"description":f.description,"source":f.source,"ttl_seconds":f.ttl_seconds} for name,f in self.feature_defs.items()},"entities":{name:{"join_key":e.join_key,"description":e.description} for name,e in self.entity_defs.items()}}
        os.makedirs("config/feature_store", exist_ok=True)
        with open("config/feature_store/features.json",'w') as f: json.dump(data,f,indent=2)
    def register_feature(self, feature): self.feature_defs[feature.name]=feature; self._save_definitions(); return True
    def register_entity(self, entity): self.entity_defs[entity.name]=entity; self._save_definitions(); return True
    def set_feature(self, feature_name, entity_key, value, timestamp=None):
        if feature_name not in self.feature_defs: raise ValueError(f"Feature {feature_name} not registered")
        fv = FeatureValue(feature_name=feature_name, entity_key=entity_key, value=value, timestamp=timestamp or int(time.time()))
        success = self.backend.put(fv)
        if self.config["enable_offline_logging"]: self.offline.write_feature_log(feature_name, entity_key, value, fv.timestamp)
        return success
    def get_feature(self, feature_name, entity_key):
        fv = self.backend.get(entity_key, feature_name)
        return fv.value if fv else None
    def get_features_batch(self, entity_keys, feature_names):
        results = {key:{} for key in entity_keys}
        for fv in self.backend.get_batch(entity_keys, feature_names):
            results[fv.entity_key][fv.feature_name] = fv.value
        return results
    def get_online_features(self, query):
        fv_dict = self.get_features_batch(query.entity_keys, query.feature_names)
        return pd.DataFrame([{query.entity_join_key: key, **features} for key,features in fv_dict.items()])
    def export_training_data(self, feature_names, start_time, end_time):
        return self.offline.export_training_data(feature_names, int(start_time.timestamp()), int(end_time.timestamp()))
    def get_feature_stats(self, feature_name):
        import pandas as pd
        path = os.path.join(self.config["offline_path"], f"{feature_name}.parquet")
        if not os.path.exists(path): return {}
        df = pd.read_parquet(path)
        values = df["value"].dropna()
        if len(values)==0: return {}
        return {"count":len(values),"mean":float(values.mean()) if pd.api.types.is_numeric_dtype(values) else None,"std":float(values.std()) if pd.api.types.is_numeric_dtype(values) else None,"min":float(values.min()) if pd.api.types.is_numeric_dtype(values) else None,"max":float(values.max()) if pd.api.types.is_numeric_dtype(values) else None,"null_count":int(df["value"].isna().sum())}

_fs_manager = None
def get_fs_manager():
    global _fs_manager
    if _fs_manager is None: _fs_manager = FeatureStoreManager()
    return _fs_manager
