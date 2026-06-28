# datalake/lake_service.py – Unified interface for Delta/Iceberg/Hudi
import json
import pandas as pd
from typing import Dict, List, Optional, Any
from .writers.delta_writer import get_delta_service
from .writers.iceberg_writer import get_iceberg_service
from .writers.hudi_writer import get_hudi_service

class DataLakeService:
    def __init__(self, config_path: str = "config/datalake/config.json"):
        self.config = self._load_config(config_path)
        self.format = self.config.get("default_format", "delta")
        self.delta = get_delta_service()
        self.iceberg = get_iceberg_service()
        self.hudi = get_hudi_service()
    
    def _load_config(self, path):
        import json, os
        default = {
            "default_format": "delta",
            "storage": "local",
            "base_path": "data/lake",
            "auto_write_enabled": True,
            "write_batch_size": 1000
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _get_service(self, format_type: str = None):
        fmt = format_type or self.format
        if fmt == "delta":
            return self.delta
        elif fmt == "iceberg":
            return self.iceberg
        elif fmt == "hudi":
            return self.hudi
        else:
            return self.delta
    
    def write_events(self, events: List[Dict], format_type: str = None) -> bool:
        svc = self._get_service(format_type)
        if format_type == "delta":
            return svc.write_events(events)
        else:
            df = pd.DataFrame(events)
            return svc.write_dataframe("events", df)
    
    def write_conversations(self, conversations: List[Dict], format_type: str = None) -> bool:
        svc = self._get_service(format_type)
        df = pd.DataFrame(conversations)
        return svc.write_dataframe("conversations", df)
    
    def write_metrics(self, metrics: List[Dict], format_type: str = None) -> bool:
        svc = self._get_service(format_type)
        df = pd.DataFrame(metrics)
        return svc.write_dataframe("metrics", df)
    
    def query(self, table: str, format_type: str = None, filter_expr: str = None, version: int = None) -> pd.DataFrame:
        svc = self._get_service(format_type)
        if format_type == "delta" and version is not None:
            return svc.time_travel(table, version)
        elif format_type == "delta":
            return svc.query(table, filter_expr)
        else:
            return svc.query(table)
    
    def get_versions(self, table: str, format_type: str = None) -> List[Dict]:
        svc = self._get_service(format_type)
        if hasattr(svc, "get_versions"):
            return svc.get_versions(table)
        return []
    
    def optimize(self, table: str, format_type: str = None) -> bool:
        svc = self._get_service(format_type)
        if hasattr(svc, "optimize"):
            return svc.optimize(table)
        return False
    
    def vacuum(self, table: str, retention_hours: int = 168, format_type: str = None) -> bool:
        svc = self._get_service(format_type)
        if hasattr(svc, "vacuum"):
            return svc.vacuum(table, retention_hours)
        return False

_lake_service = None
def get_lake_service():
    global _lake_service
    if _lake_service is None:
        _lake_service = DataLakeService()
    return _lake_service
