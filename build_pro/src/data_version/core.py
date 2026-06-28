# data_version/core.py – CrownStar Data Versioning & Lineage Engine
import os, json, time, hashlib, shutil, glob, subprocess, tempfile
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Data Models
# --------------------------------------------------------------------
class VersionBackend(Enum):
    DVC = "dvc"
    LAKEFS = "lakefs"
    DELTA_LAKE = "delta_lake"
    LOCAL = "local"

@dataclass
class DataVersion:
    version_id: str
    dataset_name: str
    tag: str
    branch: str
    commit_hash: str
    author: str
    message: str
    timestamp: int
    size_bytes: int
    file_count: int
    checksum: str
    metadata: Dict

@dataclass
class LineageEdge:
    edge_id: str
    source_type: str  # "dataset", "model", "pipeline"
    source_id: str
    target_type: str
    target_id: str
    relation: str  # "used_as_training", "produced_by", "evaluated_on"
    timestamp: int
    metadata: Dict

@dataclass
class DataQualityReport:
    dataset_name: str
    version_id: str
    passed: bool
    checks: Dict[str, Any]
    timestamp: int

# --------------------------------------------------------------------
# Abstract Version Backend
# --------------------------------------------------------------------
class VersionBackendInterface:
    def __init__(self, config: Dict):
        self.config = config

    def init_repo(self, path: str) -> bool:
        raise NotImplementedError

    def commit(self, dataset_path: str, message: str, author: str) -> DataVersion:
        raise NotImplementedError

    def tag(self, version_id: str, tag: str) -> bool:
        raise NotImplementedError

    def checkout(self, version_id: str, target_path: str) -> bool:
        raise NotImplementedError

    def diff(self, version_a: str, version_b: str) -> Dict:
        raise NotImplementedError

    def list_versions(self, dataset_name: str) -> List[DataVersion]:
        raise NotImplementedError

class LocalVersionBackend(VersionBackendInterface):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.store_root = config.get("store_root", "data/version_store")
        os.makedirs(self.store_root, exist_ok=True)
        self.manifest_path = os.path.join(self.store_root, "manifest.json")
        self._load_manifest()

    def _load_manifest(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, 'r') as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {"versions": {}, "tags": {}, "branches": {"main": []}}

    def _save_manifest(self):
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def commit(self, dataset_path: str, message: str, author: str) -> DataVersion:
        version_id = hashlib.md5(f"{dataset_path}_{time.time()}".encode()).hexdigest()[:16]
        snapshot_dir = os.path.join(self.store_root, version_id)
        os.makedirs(snapshot_dir, exist_ok=True)
        for root, dirs, files in os.walk(dataset_path):
            rel_path = os.path.relpath(root, dataset_path)
            dest_dir = os.path.join(snapshot_dir, rel_path)
            os.makedirs(dest_dir, exist_ok=True)
            for f in files:
                src = os.path.join(root, f)
                dst = os.path.join(dest_dir, f)
                if hasattr(os, 'link') and os.path.exists(dst):
                    os.link(src, dst)
                else:
                    shutil.copy2(src, dst)
        total_size = sum(os.path.getsize(os.path.join(root, f)) for root, _, files in os.walk(snapshot_dir) for f in files)
        file_count = sum(len(files) for _, _, files in os.walk(snapshot_dir))
        checksum = hashlib.md5(str(total_size).encode()).hexdigest()[:16]
        version = DataVersion(
            version_id=version_id,
            dataset_name=os.path.basename(dataset_path),
            tag="",
            branch="main",
            commit_hash=version_id,
            author=author,
            message=message,
            timestamp=int(time.time()),
            size_bytes=total_size,
            file_count=file_count,
            checksum=checksum,
            metadata={}
        )
        self.manifest["versions"][version_id] = asdict(version)
        self.manifest["branches"]["main"].append(version_id)
        self._save_manifest()
        logger.info(f"Committed version {version_id} of {dataset_path}")
        return version

    def tag(self, version_id: str, tag: str) -> bool:
        self.manifest["tags"][tag] = version_id
        self._save_manifest()
        return True

    def checkout(self, version_id: str, target_path: str) -> bool:
        src = os.path.join(self.store_root, version_id)
        if not os.path.exists(src):
            return False
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        shutil.copytree(src, target_path)
        return True

    def diff(self, version_a: str, version_b: str) -> Dict:
        path_a = os.path.join(self.store_root, version_a)
        path_b = os.path.join(self.store_root, version_b)
        files_a = set()
        files_b = set()
        for root, _, files in os.walk(path_a):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), path_a)
                files_a.add(rel)
        for root, _, files in os.walk(path_b):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), path_b)
                files_b.add(rel)
        added = files_b - files_a
        removed = files_a - files_b
        common = files_a & files_b
        changed = []
        for f in common:
            size_a = os.path.getsize(os.path.join(path_a, f))
            size_b = os.path.getsize(os.path.join(path_b, f))
            if size_a != size_b:
                changed.append(f)
        return {"added": list(added), "removed": list(removed), "changed": changed}

    def list_versions(self, dataset_name: str) -> List[DataVersion]:
        versions = []
        for v in self.manifest["versions"].values():
            if v["dataset_name"] == dataset_name:
                versions.append(DataVersion(**v))
        return versions

# --------------------------------------------------------------------
# Lineage Tracker
# --------------------------------------------------------------------
class LineageTracker:
    def __init__(self, storage_path="data/version_store/lineage.json"):
        self.storage_path = storage_path
        self.edges: List[LineageEdge] = []
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.edges = [LineageEdge(**e) for e in data]

    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump([asdict(e) for e in self.edges], f, indent=2)

    def add_edge(self, source_type: str, source_id: str, target_type: str, target_id: str,
                 relation: str, metadata: Dict = None) -> str:
        edge_id = hashlib.md5(f"{source_type}_{source_id}_{target_type}_{target_id}_{time.time()}".encode()).hexdigest()[:16]
        edge = LineageEdge(
            edge_id=edge_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation=relation,
            timestamp=int(time.time()),
            metadata=metadata or {}
        )
        self.edges.append(edge)
        self._save()
        return edge_id

    def get_lineage(self, node_id: str, node_type: str, direction: str = "both") -> List[LineageEdge]:
        if direction in ("upstream", "both"):
            upstream = [e for e in self.edges if e.target_type == node_type and e.target_id == node_id]
        else:
            upstream = []
        if direction in ("downstream", "both"):
            downstream = [e for e in self.edges if e.source_type == node_type and e.source_id == node_id]
        else:
            downstream = []
        return upstream + downstream

    def get_model_lineage(self, model_id: str, version_id: str) -> Dict:
        upstream = self.get_lineage(version_id, "model_version", "upstream")
        downstream = self.get_lineage(version_id, "model_version", "downstream")
        return {
            "training_datasets": [e.source_id for e in upstream if e.relation == "trained_on"],
            "evaluation_datasets": [e.source_id for e in upstream if e.relation == "evaluated_on"],
            "predictions": [e.target_id for e in downstream if e.relation == "used_for_prediction"]
        }

# --------------------------------------------------------------------
# Data Quality Validator
# --------------------------------------------------------------------
class DataQualityValidator:
    @staticmethod
    def validate_schema(data_path: str, expected_schema: Dict) -> Tuple[bool, Dict]:
        import pandas as pd
        try:
            if data_path.endswith('.csv'):
                df = pd.read_csv(data_path, nrows=10)
            elif data_path.endswith('.parquet'):
                df = pd.read_parquet(data_path)
            else:
                return False, {"error": "Unsupported format"}
            actual_columns = df.columns.tolist()
            expected_columns = expected_schema.get("columns", [])
            if set(actual_columns) != set(expected_columns):
                return False, {"missing": list(set(expected_columns) - set(actual_columns)),
                              "extra": list(set(actual_columns) - set(expected_columns))}
            return True, {"message": "Schema matches"}
        except Exception as e:
            return False, {"error": str(e)}

    @staticmethod
    def check_null_counts(data_path: str, threshold: float = 0.1) -> Dict:
        import pandas as pd
        df = pd.read_csv(data_path) if data_path.endswith('.csv') else pd.read_parquet(data_path)
        null_frac = df.isnull().sum() / len(df)
        problematic = {col: float(frac) for col, frac in null_frac.items() if frac > threshold}
        return {"passed": len(problematic) == 0, "high_null_columns": problematic}

    @staticmethod
    def detect_anomalies(data_path: str, method: str = "zscore", threshold: float = 3.0) -> Dict:
        import pandas as pd
        df = pd.read_csv(data_path) if data_path.endswith('.csv') else pd.read_parquet(data_path)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        anomalies = {}
        for col in numeric_cols:
            zscores = np.abs((df[col] - df[col].mean()) / df[col].std())
            anomalies[col] = int((zscores > threshold).sum())
        return {"anomaly_counts": anomalies, "total": sum(anomalies.values())}

# --------------------------------------------------------------------
# Data Version Manager (orchestrator)
# --------------------------------------------------------------------
class DataVersionManager:
    def __init__(self, config_path="config/data_version/config.json"):
        self.config = self._load_config(config_path)
        self.backend = self._init_backend()
        self.lineage = LineageTracker()
        self.validator = DataQualityValidator()

    def _load_config(self, path):
        default = {
            "backend": "local",
            "store_root": "data/version_store",
            "default_branch": "main",
            "quality": {
                "validate_schema": True,
                "check_nulls": True,
                "anomaly_detection": True,
                "null_threshold": 0.1
            }
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def _init_backend(self):
        backend_type = self.config["backend"]
        if backend_type == "local":
            return LocalVersionBackend({"store_root": self.config["store_root"]})
        else:
            return LocalVersionBackend({"store_root": self.config["store_root"]})

    def commit_dataset(self, dataset_path: str, message: str, author: str, run_quality: bool = True) -> DataVersion:
        if run_quality:
            schema_file = os.path.join(dataset_path, "schema.json")
            if os.path.exists(schema_file):
                with open(schema_file, 'r') as f:
                    schema = json.load(f)
                valid, schema_report = self.validator.validate_schema(dataset_path, schema)
                if not valid:
                    raise ValueError(f"Schema validation failed: {schema_report}")
            null_report = self.validator.check_null_counts(dataset_path, self.config["quality"]["null_threshold"])
            if not null_report["passed"]:
                logger.warning(f"Null check warnings: {null_report['high_null_columns']}")
            anomaly_report = self.validator.detect_anomalies(dataset_path)
            if anomaly_report["total"] > 0:
                logger.warning(f"Anomalies detected: {anomaly_report['anomaly_counts']}")
        version = self.backend.commit(dataset_path, message, author)
        return version

    def tag_version(self, version_id: str, tag: str) -> bool:
        return self.backend.tag(version_id, tag)

    def checkout(self, version_id: str, target_path: str) -> bool:
        return self.backend.checkout(version_id, target_path)

    def diff(self, version_a: str, version_b: str) -> Dict:
        return self.backend.diff(version_a, version_b)

    def list_versions(self, dataset_name: str) -> List[DataVersion]:
        return self.backend.list_versions(dataset_name)

    def link_dataset_to_model(self, dataset_version_id: str, model_version_id: str, relation: str = "trained_on", metadata: Dict = None):
        return self.lineage.add_edge("dataset_version", dataset_version_id, "model_version", model_version_id, relation, metadata)

    def get_model_lineage(self, model_version_id: str) -> Dict:
        return self.lineage.get_model_lineage("", model_version_id)

    def get_lineage_graph(self, node_id: str, node_type: str) -> List[LineageEdge]:
        return self.lineage.get_lineage(node_id, node_type, "both")

_data_version_manager = None
def get_data_version_manager():
    global _data_version_manager
    if _data_version_manager is None:
        _data_version_manager = DataVersionManager()
    return _data_version_manager
