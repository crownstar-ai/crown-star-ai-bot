# mlflow/service.py – MLflow tracking and model registry wrapper
import os
import json
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.entities import RunStatus
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

class MLflowService:
    def __init__(self, config_path: str = "config/mlflow/config.json"):
        self.config = self._load_config(config_path)
        self._setup_mlflow()
        self.client = MlflowClient(tracking_uri=self.config["tracking_uri"])
    
    def _load_config(self, path):
        default = {
            "tracking_uri": "sqlite:///data/mlflow/mlflow.db",
            "artifact_uri": "file:./data/mlflow/artifacts",
            "registry_uri": "sqlite:///data/mlflow/mlflow.db",
            "experiment_name": "crownstar",
            "s3_bucket": None,
            "s3_endpoint_url": None
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _setup_mlflow(self):
        mlflow.set_tracking_uri(self.config["tracking_uri"])
        mlflow.set_registry_uri(self.config["registry_uri"])
        if self.config["s3_bucket"]:
            os.environ["MLFLOW_S3_ENDPOINT_URL"] = self.config.get("s3_endpoint_url", "")
    
    def get_or_create_experiment(self, name: str = None) -> str:
        exp_name = name or self.config["experiment_name"]
        exp = mlflow.get_experiment_by_name(exp_name)
        if exp:
            return exp.experiment_id
        return mlflow.create_experiment(exp_name, artifact_location=self.config["artifact_uri"])
    
    def start_run(self, experiment_id: str = None, run_name: str = None, tags: Dict = None):
        exp_id = experiment_id or self.get_or_create_experiment()
        return mlflow.start_run(experiment_id=exp_id, run_name=run_name, tags=tags)
    
    def log_params(self, params: Dict):
        mlflow.log_params(params)
    
    def log_metrics(self, metrics: Dict, step: int = None):
        mlflow.log_metrics(metrics, step=step)
    
    def log_artifact(self, local_path: str, artifact_path: str = None):
        mlflow.log_artifact(local_path, artifact_path=artifact_path)
    
    def log_model(self, model_path: str, model_name: str, registered_model_name: str = None):
        mlflow.log_artifact(model_path, artifact_path="model")
        if registered_model_name:
            mlflow.register_model(f"runs:/{mlflow.active_run().info.run_id}/model", registered_model_name)
    
    def end_run(self, status: str = "FINISHED"):
        mlflow.end_run(status=status)
    
    def search_runs(self, experiment_ids: List[str], filter_string: str = None) -> List[Dict]:
        runs = mlflow.search_runs(experiment_ids=experiment_ids, filter_string=filter_string)
        return runs.to_dict(orient="records")
    
    def get_run(self, run_id: str) -> Dict:
        run = mlflow.get_run(run_id)
        return {
            "run_id": run.info.run_id,
            "experiment_id": run.info.experiment_id,
            "status": run.info.status,
            "start_time": run.info.start_time,
            "end_time": run.info.end_time,
            "params": run.data.params,
            "metrics": run.data.metrics,
            "tags": run.data.tags
        }
    
    def register_model(self, local_path: str, model_name: str, version_description: str = None) -> Dict:
        """Register a model from local path"""
        with mlflow.start_run(run_name="model_registration") as run:
            mlflow.log_artifact(local_path, artifact_path="model")
            result = mlflow.register_model(f"runs:/{run.info.run_id}/model", model_name)
            if version_description:
                self.client.update_model_version(model_name, result.version, description=version_description)
            return {"name": result.name, "version": result.version, "stage": result.stage}
    
    def register_model_from_run(self, run_id: str, model_name: str) -> Dict:
        result = mlflow.register_model(f"runs:/{run_id}/model", model_name)
        return {"name": result.name, "version": result.version, "stage": result.stage}
    
    def list_models(self, max_results: int = 100) -> List[Dict]:
        models = self.client.search_registered_models(max_results=max_results)
        return [{"name": m.name, "latest_versions": [{"version": v.version, "stage": v.stage, "run_id": v.run_id} for v in m.latest_versions]} for m in models]
    
    def get_model_versions(self, model_name: str) -> List[Dict]:
        versions = self.client.search_model_versions(f"name='{model_name}'")
        return [{"version": v.version, "stage": v.stage, "run_id": v.run_id, "status": v.status, "description": v.description} for v in versions]
    
    def promote_model_version(self, model_name: str, version: int, stage: str) -> Dict:
        """Transition model version stage (Staging, Production, Archived)"""
        self.client.transition_model_version_stage(model_name, version, stage)
        return {"model_name": model_name, "version": version, "stage": stage}
    
    def load_model(self, model_name: str, stage: str = "Production", version: int = None) -> Any:
        """Load model from registry (returns PyFunc model)"""
        if version:
            model_uri = f"models:/{model_name}/{version}"
        else:
            model_uri = f"models:/{model_name}/{stage}"
        return mlflow.pyfunc.load_model(model_uri)
    
    def get_production_model(self, model_name: str) -> Optional[Dict]:
        versions = self.client.search_model_versions(f"name='{model_name}' and stage='Production'")
        if versions:
            v = versions[0]
            return {"version": v.version, "run_id": v.run_id, "status": v.status}
        return None

_mlflow_service = None
def get_mlflow_service():
    global _mlflow_service
    if _mlflow_service is None:
        _mlflow_service = MLflowService()
    return _mlflow_service
