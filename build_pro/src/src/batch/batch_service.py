# batch/batch_service.py – Unified batch service
import json
import os
from typing import Dict, List, Optional
from .providers.base import BatchJob
from .providers.aws_batch import AWSBatchProvider
from .providers.azure_batch import AzureBatchProvider
from .providers.gcp_batch import GCPBatchProvider
from .providers.local_batch import LocalBatchProvider

class BatchService:
    def __init__(self, config_path: str = "config/batch/config.json"):
        self.config = self._load_config(config_path)
        self.provider = self._get_provider()
    
    def _load_config(self, path):
        default = {
            "provider": "local",
            "aws": {"region": "us-east-1", "job_queue": "crownstar-queue", "job_definition": "crownstar-job"},
            "azure": {"account_name": "", "account_key": "", "account_url": "", "pool_id": "crownstar-pool"},
            "gcp": {"project_id": "", "region": "us-central1", "service_account": ""}
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _get_provider(self):
        provider_name = self.config["provider"]
        if provider_name == "aws":
            cfg = self.config["aws"]
            return AWSBatchProvider(cfg["region"], cfg["job_queue"], cfg["job_definition"])
        elif provider_name == "azure":
            cfg = self.config["azure"]
            return AzureBatchProvider(cfg["account_name"], cfg["account_key"], cfg["account_url"], cfg["pool_id"])
        elif provider_name == "gcp":
            cfg = self.config["gcp"]
            return GCPBatchProvider(cfg["project_id"], cfg.get("region", "us-central1"), cfg.get("service_account"))
        else:
            return LocalBatchProvider()
    
    def submit_job(self, job_name: str, job_type: str, parameters: Dict = None) -> str:
        """Submit a predefined job type (analytics, backup, training, report)"""
        job_definitions = {
            "analytics": ["python", "-m", "src.batch.jobs.analytics_job"],
            "backup": ["python", "-m", "src.batch.jobs.backup_job"],
            "training": ["python", "-m", "src.batch.jobs.training_job"],
            "report": ["python", "-m", "src.batch.jobs.report_job"]
        }
        command = job_definitions.get(job_type, ["echo", "Unknown job type"])
        if parameters:
            command += [f"--{k}={v}" for k, v in parameters.items()]
        return self.provider.submit_job(job_name, command)
    
    def submit_custom(self, job_name: str, command: List[str], environment: Dict = None) -> str:
        return self.provider.submit_job(job_name, command, environment)
    
    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        return self.provider.list_jobs(limit)
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        return self.provider.get_job_status(job_id)
    
    def get_job_logs(self, job_id: str, tail_lines: int = 100) -> str:
        return self.provider.get_job_logs(job_id, tail_lines)
    
    def terminate_job(self, job_id: str) -> bool:
        return self.provider.terminate_job(job_id)

_batch_service = None
def get_batch_service():
    global _batch_service
    if _batch_service is None:
        _batch_service = BatchService()
    return _batch_service
