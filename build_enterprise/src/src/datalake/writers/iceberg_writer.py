# datalake/writers/iceberg_writer.py – Iceberg table writer (stub)
import os
import pandas as pd
from typing import Dict, List, Optional
from pathlib import Path

class IcebergService:
    def __init__(self, warehouse_path: str = "data/lake/iceberg", catalog_name: str = "crownstar"):
        self.warehouse_path = Path(warehouse_path)
        self.warehouse_path.mkdir(parents=True, exist_ok=True)
        self.catalog_name = catalog_name
        # In real implementation, use pyiceberg or Java Gateway
        self.tables = {}
    
    def create_table(self, table_name: str, schema: Dict) -> bool:
        """Create Iceberg table with schema"""
        table_dir = self.warehouse_path / table_name
        table_dir.mkdir(exist_ok=True)
        metadata = {"name": table_name, "schema": schema, "created": str(datetime.utcnow())}
        with open(table_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)
        self.tables[table_name] = {"path": table_dir, "metadata": metadata}
        return True
    
    def write_dataframe(self, table_name: str, df: pd.DataFrame, mode: str = "append") -> bool:
        """Write to Iceberg table (parquet files)"""
        table_dir = self.warehouse_path / table_name
        if not table_dir.exists():
            self.create_table(table_name, {col: "string" for col in df.columns})
        # Write as Parquet
        partition = datetime.utcnow().strftime("%Y%m%d")
        parquet_dir = table_dir / partition
        parquet_dir.mkdir(exist_ok=True)
        file_name = f"{datetime.utcnow().timestamp()}.parquet"
        df.to_parquet(parquet_dir / file_name, index=False)
        return True
    
    def query(self, table_name: str, sql: str = None) -> pd.DataFrame:
        """Read Iceberg table as DataFrame (simple)"""
        table_dir = self.warehouse_path / table_name
        if not table_dir.exists():
            return pd.DataFrame()
        # Read all Parquet files
        dfs = []
        for parquet_file in table_dir.glob("**/*.parquet"):
            dfs.append(pd.read_parquet(parquet_file))
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    def list_tables(self) -> List[str]:
        return [p.name for p in self.warehouse_path.iterdir() if p.is_dir()]

_iceberg_service = None
def get_iceberg_service():
    global _iceberg_service
    if _iceberg_service is None:
        _iceberg_service = IcebergService()
    return _iceberg_service
