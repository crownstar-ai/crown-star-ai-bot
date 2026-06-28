# lineage/service.py – Track data lineage for model training, inference, API calls
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from .openlineage.emitter import get_emitter
from .marquez.client import get_marquez

class LineageService:
    def __init__(self):
        self.emitter = get_emitter()
        self.marquez = get_marquez()
    
    def track_api_call(self, user_id: str, query: str, response: str, model: str, modules: List[str]):
        """Emit lineage for an API chat request"""
        input_dataset = {
            "namespace": "crownstar",
            "name": f"user_input_{hashlib.md5(user_id.encode()).hexdigest()[:8]}",
            "facets": {
                "schema": {"fields": [{"name": "query", "type": "string"}]}
            }
        }
        output_dataset = {
            "namespace": "crownstar",
            "name": f"model_output_{model}_{int(time.time())}",
            "facets": {
                "schema": {"fields": [{"name": "response", "type": "string"}]}
            }
        }
        self.emitter.emit(
            "START",
            {
                "job_name": f"api_chat.{model}",
                "inputs": [input_dataset],
                "outputs": [output_dataset],
                "facets": {
                    "crownstar": {
                        "user_id": user_id,
                        "modules_active": modules,
                        "query_length": len(query),
                        "response_length": len(response)
                    }
                }
            }
        )
    
    def track_model_training(self, model_name: str, dataset_path: str, hyperparams: Dict):
        """Emit lineage for model fine‑tuning"""
        input_dataset = {"namespace": "crownstar", "name": f"training_data_{dataset_path.replace('/','_')}"}
        output_dataset = {"namespace": "crownstar", "name": f"model_{model_name}_{int(time.time())}"}
        self.emitter.emit(
            "COMPLETE",
            {
                "job_name": f"train.{model_name}",
                "inputs": [input_dataset],
                "outputs": [output_dataset],
                "facets": {"hyperparameters": hyperparams}
            }
        )
    
    def get_lineage_graph(self, dataset_name: str = None, job_name: str = None) -> Dict:
        if dataset_name:
            return self.marquez.get_lineage_graph("crownstar", dataset=dataset_name)
        elif job_name:
            return self.marquez.get_lineage_graph("crownstar", job=job_name)
        return {"error": "Specify dataset or job"}

_lineage = None
def get_lineage():
    global _lineage
    if _lineage is None:
        _lineage = LineageService()
    return _lineage
