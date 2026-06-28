# synthetic/service.py – Generate synthetic data (Faker, distributions, time series)
import json
import random
import datetime
import hashlib
from typing import Dict, List, Any, Optional, Union
import numpy as np
from pathlib import Path

# Lazy import Faker to avoid heavy dep if not installed
_faker = None
def _get_faker():
    global _faker
    if _faker is None:
        try:
            from faker import Faker
            _faker = Faker()
        except ImportError:
            raise ImportError("Faker not installed. Install with: pip install Faker")
    return _faker

class SyntheticDataGenerator:
    """Generate synthetic data based on schema definitions"""
    
    @staticmethod
    def generate_value(field_type: str, params: Dict = None) -> Any:
        params = params or {}
        if field_type == "name":
            return _get_faker().name()
        elif field_type == "first_name":
            return _get_faker().first_name()
        elif field_type == "last_name":
            return _get_faker().last_name()
        elif field_type == "email":
            return _get_faker().email()
        elif field_type == "phone":
            return _get_faker().phone_number()
        elif field_type == "address":
            return _get_faker().address()
        elif field_type == "city":
            return _get_faker().city()
        elif field_type == "country":
            return _get_faker().country()
        elif field_type == "date":
            start = params.get("start", "-30y")
            end = params.get("end", "now")
            return _get_faker().date_between(start_date=start, end_date=end).isoformat()
        elif field_type == "datetime":
            return _get_faker().date_time_this_year().isoformat()
        elif field_type == "int":
            low = params.get("min", 0)
            high = params.get("max", 100)
            return random.randint(low, high)
        elif field_type == "float":
            low = params.get("min", 0.0)
            high = params.get("max", 100.0)
            return random.uniform(low, high)
        elif field_type == "boolean":
            return random.choice([True, False])
        elif field_type == "string":
            length = params.get("length", 20)
            return _get_faker().pystr(min_chars=1, max_chars=length)
        elif field_type == "text":
            sentences = params.get("sentences", 3)
            return _get_faker().paragraph(nb_sentences=sentences)
        elif field_type == "uuid":
            return str(_get_faker().uuid4())
        elif field_type == "ipv4":
            return _get_faker().ipv4()
        elif field_type == "user_agent":
            return _get_faker().user_agent()
        elif field_type == "choice":
            choices = params.get("choices", ["a", "b", "c"])
            return random.choice(choices)
        elif field_type == "sentence":
            return _get_faker().sentence()
        elif field_type == "paragraph":
            return _get_faker().paragraph()
        elif field_type == "time_series":
            # Generate list of values over time (simplified)
            length = params.get("length", 24)
            base = params.get("base", 0)
            trend = params.get("trend", 0)
            seasonality = params.get("seasonality", 0)
            values = []
            for i in range(length):
                val = base + trend * i + seasonality * np.sin(2*np.pi*i/24)
                values.append(val)
            return values
        elif field_type == "object":
            # Nested object
            sub_schema = params.get("schema", {})
            return SyntheticDataGenerator.generate_object(sub_schema)
        elif field_type == "array":
            count = params.get("count", random.randint(1, 5))
            item_type = params.get("item_type", "string")
            return [SyntheticDataGenerator.generate_value(item_type, params.get("item_params", {})) for _ in range(count)]
        else:
            return f"unknown_type_{field_type}"
    
    @staticmethod
    def generate_object(schema: Dict) -> Dict:
        """Generate a dictionary from a JSON schema definition"""
        obj = {}
        for field, config in schema.items():
            if isinstance(config, dict) and "type" in config:
                obj[field] = SyntheticDataGenerator.generate_value(config["type"], config.get("params", {}))
            elif isinstance(config, dict):
                # Recursive object
                obj[field] = SyntheticDataGenerator.generate_object(config)
            else:
                # Shorthand: field: "type"
                obj[field] = SyntheticDataGenerator.generate_value(config, {})
        return obj
    
    @staticmethod
    def generate_list(schema: Dict, count: int) -> List[Dict]:
        """Generate a list of synthetic objects"""
        return [SyntheticDataGenerator.generate_object(schema) for _ in range(count)]

class TestDataManager:
    def __init__(self, base_dir: str = "data/synthetic"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir = self.base_dir / "versions"
        self.versions_dir.mkdir(exist_ok=True)
    
    def create_version(self, name: str, data: Any, metadata: Dict = None) -> str:
        """Save a snapshot of test data with version name"""
        version_path = self.versions_dir / f"{name}.json"
        version_info = {
            "name": name,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "data": data
        }
        with open(version_path, "w") as f:
            json.dump(version_info, f, indent=2, default=str)
        return name
    
    def load_version(self, name: str) -> Optional[Dict]:
        version_path = self.versions_dir / f"{name}.json"
        if not version_path.exists():
            return None
        with open(version_path, "r") as f:
            return json.load(f)
    
    def list_versions(self) -> List[str]:
        return [p.stem for p in self.versions_dir.glob("*.json")]
    
    def delete_version(self, name: str) -> bool:
        version_path = self.versions_dir / f"{name}.json"
        if version_path.exists():
            version_path.unlink()
            return True
        return False
    
    def restore_version(self, name: str, target_path: str = None) -> Optional[Dict]:
        """Restore a version to the specified target (or return data)"""
        version = self.load_version(name)
        if not version:
            return None
        if target_path:
            with open(target_path, "w") as f:
                json.dump(version["data"], f, indent=2)
        return version["data"]
    
    def rollback_to_version(self, name: str, current_path: str) -> bool:
        """Replace current data file with previous version"""
        data = self.restore_version(name)
        if data is None:
            return False
        with open(current_path, "w") as f:
            json.dump(data, f, indent=2)
        return True

_synth = None
_data_mgr = None
def get_synth():
    global _synth
    if _synth is None:
        _synth = SyntheticDataGenerator()
    return _synth

def get_data_manager():
    global _data_mgr
    if _data_mgr is None:
        _data_mgr = TestDataManager()
    return _data_mgr
