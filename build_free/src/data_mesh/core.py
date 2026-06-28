# data_mesh/core.py – CrownStar Cross‑Cloud Data Mesh & Federated Query Engine
import os, json, time, hashlib, re, threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import sqlparse
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Data Source Abstraction
# --------------------------------------------------------------------
class DataSourceType(Enum):
    POSTGRES = "postgresql"
    MYSQL = "mysql"
    S3_PARQUET = "s3_parquet"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    CROWNSTAR_VECTOR = "crownstar_vector"
    REST_API = "rest_api"

@dataclass
class DataSource:
    name: str
    type: DataSourceType
    connection_params: Dict
    domain: str          # data mesh domain (e.g., "sales", "analytics")
    tags: List[str]
    priority: int = 0
    max_rows: int = 10000

@dataclass
class QueryResult:
    query_id: str
    sql: str
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float
    source_hints: List[str]
    cached: bool

class DataSourceConnector(ABC):
    @abstractmethod
    def execute(self, sql: str, limit: int) -> QueryResult:
        pass

class PostgresConnector(DataSourceConnector):
    def __init__(self, conn_params):
        import psycopg2
        self.conn_params = conn_params
    def execute(self, sql, limit):
        # Placeholder – real implementation would connect and execute
        return QueryResult(
            query_id=hashlib.md5(sql.encode()).hexdigest()[:16],
            sql=sql,
            columns=["col1", "col2"],
            rows=[],
            row_count=0,
            execution_time_ms=10,
            source_hints=["postgres"],
            cached=False
        )

class S3ParquetConnector(DataSourceConnector):
    def __init__(self, conn_params):
        import pyarrow.parquet as pq
        import boto3
        self.bucket = conn_params.get("bucket")
        self.prefix = conn_params.get("prefix")
    def execute(self, sql, limit):
        # Would use DuckDB or PyArrow to query Parquet
        return QueryResult(...)

# --------------------------------------------------------------------
# Query Planner (Cost‑Based Optimization)
# --------------------------------------------------------------------
class QueryPlanner:
    def __init__(self, sources: List[DataSource]):
        self.sources = {s.name: s for s in sources}

    def plan(self, sql: str) -> Dict:
        """Parse SQL, determine which sources to query, estimate costs."""
        # Simplified: extract table names (FROM clause) and match to sources
        tables = re.findall(r'FROM\s+([a-zA-Z0-9_]+)', sql, re.IGNORECASE)
        used_sources = []
        for table in tables:
            if table in self.sources:
                used_sources.append(self.sources[table])
            else:
                # Try to infer by domain or tag
                for src in self.sources.values():
                    if table in src.tags or src.domain == table:
                        used_sources.append(src)
                        break
        # Estimate cost (rows * priority)
        estimated_cost = sum(s.priority * 1000 for s in used_sources)
        return {
            "sql": sql,
            "sources": [s.name for s in used_sources],
            "estimated_cost": estimated_cost,
            "estimated_rows": 1000  # placeholder
        }

# --------------------------------------------------------------------
# Federated Query Engine (Core)
# --------------------------------------------------------------------
class FederatedQueryEngine:
    def __init__(self, config_path="config/data_mesh/sources.json"):
        self.sources: List[DataSource] = []
        self.connectors: Dict[str, DataSourceConnector] = {}
        self.query_cache = {}
        self._load_config(config_path)
        self._init_connectors()
        self.planner = QueryPlanner(self.sources)

    def _load_config(self, path):
        default = {
            "sources": [
                {
                    "name": "analytics_warehouse",
                    "type": "postgresql",
                    "connection_params": {"host": "localhost", "database": "crownstar"},
                    "domain": "analytics",
                    "tags": ["logs", "metrics"],
                    "priority": 1
                },
                {
                    "name": "vector_index",
                    "type": "crownstar_vector",
                    "connection_params": {"index_path": "data/vectors/crownstar_index.faiss"},
                    "domain": "embeddings",
                    "tags": ["vectors", "search"],
                    "priority": 2
                }
            ]
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                # Merge
                if "sources" in user:
                    default["sources"] = user["sources"]
        for src in default["sources"]:
            self.sources.append(DataSource(
                name=src["name"],
                type=DataSourceType(src["type"]),
                connection_params=src["connection_params"],
                domain=src.get("domain", "default"),
                tags=src.get("tags", []),
                priority=src.get("priority", 0)
            ))

    def _init_connectors(self):
        for src in self.sources:
            if src.type == DataSourceType.POSTGRES:
                self.connectors[src.name] = PostgresConnector(src.connection_params)
            elif src.type == DataSourceType.S3_PARQUET:
                self.connectors[src.name] = S3ParquetConnector(src.connection_params)
            # Additional connectors would be added

    def execute(self, sql: str, use_cache: bool = True, limit: int = 1000) -> QueryResult:
        """Execute SQL query across one or more data sources (federated)."""
        start = time.perf_counter()
        query_id = hashlib.md5(f"{sql}_{time.time()}".encode()).hexdigest()[:16]
        # Check cache
        cache_key = hashlib.md5(sql.encode()).hexdigest()
        if use_cache and cache_key in self.query_cache:
            cached = self.query_cache[cache_key]
            cached.query_id = query_id
            cached.cached = True
            logger.info(f"Query {query_id} served from cache")
            return cached
        # Plan query
        plan = self.planner.plan(sql)
        if not plan["sources"]:
            raise ValueError(f"No data source found for query: {sql}")
        # Execute on each source and merge results (simplified: first source only)
        primary_source = plan["sources"][0]
        connector = self.connectors.get(primary_source)
        if not connector:
            raise ValueError(f"No connector for source {primary_source}")
        result = connector.execute(sql, limit)
        result.query_id = query_id
        result.cached = False
        # Cache result
        if use_cache:
            self.query_cache[cache_key] = result
            # Trim cache size
            if len(self.query_cache) > 100:
                oldest = next(iter(self.query_cache))
                del self.query_cache[oldest]
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Query {query_id} executed in {result.execution_time_ms:.2f}ms, rows: {result.row_count}")
        return result

    def get_sources(self) -> List[Dict]:
        return [asdict(s) for s in self.sources]

    def get_schema(self, source_name: str) -> Dict:
        """Retrieve schema (tables/columns) from a data source."""
        # Placeholder – would query information_schema
        return {"source": source_name, "tables": []}

    def add_source(self, source: DataSource) -> bool:
        self.sources.append(source)
        self._init_connectors()  # reconnect
        self._save_config()
        return True

    def _save_config(self):
        config = {"sources": [{"name": s.name, "type": s.type.value, "connection_params": s.connection_params, "domain": s.domain, "tags": s.tags, "priority": s.priority} for s in self.sources]}
        with open("config/data_mesh/sources.json", 'w') as f:
            json.dump(config, f, indent=2)

_data_mesh_engine = None
def get_data_mesh_engine():
    global _data_mesh_engine
    if _data_mesh_engine is None:
        _data_mesh_engine = FederatedQueryEngine()
    return _data_mesh_engine
