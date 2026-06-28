# datalake/writers/delta_writer.py – Delta Lake writer/reader
import os
import json
import pandas as pd
from deltalake import DeltaTable, write_deltalake
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
from typing import Dict, List, Optional, Any
from pathlib import Path

class DeltaLakeService:
    def __init__(self, base_path: str = "data/lake/delta"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_table_path(self, table_name: str) -> Path:
        return self.base_path / table_name
    
    def write_dataframe(self, table_name: str, df: pd.DataFrame, mode: str = "append", partition_by: List[str] = None) -> bool:
        """Write pandas DataFrame as Delta table"""
        path = self._get_table_path(table_name)
        try:
            write_deltalake(
                path,
                df,
                mode=mode,
                partition_by=partition_by,
                engine='rust'
            )
            return True
        except Exception as e:
            print(f"Delta write error: {e}")
            return False
    
    def write_events(self, events: List[Dict], table_name: str = "events") -> bool:
        """Write list of event dicts to Delta table"""
        if not events:
            return True
        df = pd.DataFrame(events)
        # Ensure timestamp column
        if 'timestamp' not in df.columns:
            df['timestamp'] = datetime.utcnow().isoformat()
        return self.write_dataframe(table_name, df, mode="append", partition_by=["event_type"])
    
    def write_conversations(self, conversations: List[Dict], table_name: str = "conversations") -> bool:
        df = pd.DataFrame(conversations)
        return self.write_dataframe(table_name, df, mode="append", partition_by=["date"])
    
    def write_metrics(self, metrics: List[Dict], table_name: str = "metrics") -> bool:
        df = pd.DataFrame(metrics)
        return self.write_dataframe(table_name, df, mode="append", partition_by=["metric_type"])
    
    def query(self, table_name: str, filter_expr: str = None) -> pd.DataFrame:
        """Query Delta table (returns DataFrame)"""
        path = self._get_table_path(table_name)
        if not path.exists():
            return pd.DataFrame()
        dt = DeltaTable(path)
        if filter_expr:
            # PyArrow filter (simplified)
            df = dt.to_pandas()
            return df.query(filter_expr) if filter_expr else df
        return dt.to_pandas()
    
    def get_versions(self, table_name: str) -> List[Dict]:
        """List versions for time travel"""
        path = self._get_table_path(table_name)
        if not path.exists():
            return []
        dt = DeltaTable(path)
        return [{"version": v.version, "timestamp": v.timestamp.isoformat()} for v in dt.history()]
    
    def time_travel(self, table_name: str, version: int) -> pd.DataFrame:
        """Read table at specific version"""
        path = self._get_table_path(table_name)
        dt = DeltaTable(path, version=version)
        return dt.to_pandas()
    
    def vacuum(self, table_name: str, retention_hours: int = 168) -> bool:
        """Remove old files (default 7 days)"""
        path = self._get_table_path(table_name)
        if not path.exists():
            return False
        dt = DeltaTable(path)
        dt.vacuum(retention_hours=retention_hours)
        return True
    
    def optimize(self, table_name: str) -> bool:
        """Compact small files (simplified)"""
        # In production would use DeltaTable.optimize() (Rust)
        print(f"Optimize called for {table_name} – full compaction requires DeltaTable.optimize()")
        return True

_delta_service = None
def get_delta_service():
    global _delta_service
    if _delta_service is None:
        _delta_service = DeltaLakeService()
    return _delta_service
