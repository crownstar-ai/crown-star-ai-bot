# batch/providers/gcp_batch.py – Google Cloud Batch integration
import os
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime
from .base import BatchProvider, BatchJob

class GCPBatchProvider(BatchProvider):
    def __init__(self, project_id: str, region: str = "us-central1", service_account: str = None):
        self.project_id = project_id
        self.region = region
        self.service_account = service_account
        self.api_endpoint = f"https://batch.googleapis.com/v1/projects/{project_id}/locations/{region}/jobs"
        self.access_token = None
        self._get_token()
    
    def _get_token(self):
        import subprocess
        try:
            result = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
            self.access_token = result.stdout.strip()
        except:
            self.access_token = os.environ.get("GCP_ACCESS_TOKEN")
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
    
    def submit_job(self, job_name: str, command: List[str], environment: Dict = None, resources: Dict = None) -> str:
        job_body = {
            "taskGroups": [{
                "taskSpec": {
                    "runnables": [{
                        "script": {"text": " ".join(command)}
                    }],
                    "environment": {"variables": environment or {}},
                    "computeResource": {
                        "cpuMilli": (resources.get("vcpus", 1) * 1000) if resources else 1000,
                        "memoryMib": resources.get("memory_mb", 512) if resources else 512
                    }
                },
                "taskCount": 1
            }],
            "logsPolicy": {"destination": "CLOUD_LOGGING"}
        }
        resp = requests.post(f"{self.api_endpoint}?jobId={job_name}", headers=self._headers(), json=job_body)
        if resp.status_code == 200:
            return resp.json().get("name", "").split("/")[-1]
        return None
    
    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        resp = requests.get(f"{self.api_endpoint}", headers=self._headers())
        if resp.status_code != 200:
            return []
        jobs = resp.json().get("jobs", [])
        result = []
        for job in jobs[:limit]:
            status = job.get("status", {}).get("state", "UNKNOWN")
            result.append(BatchJob(
                job_id=job["name"].split("/")[-1],
                name=job["name"],
                status=status,
                created_at=datetime.fromisoformat(job["createTime"].replace("Z", "+00:00"))
            ))
        return result
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        resp = requests.get(f"{self.api_endpoint}/{job_id}", headers=self._headers())
        if resp.status_code != 200:
            return None
        job = resp.json()
        return BatchJob(
            job_id=job_id,
            name=job["name"],
            status=job.get("status", {}).get("state", "UNKNOWN"),
            created_at=datetime.fromisoformat(job["createTime"].replace("Z", "+00:00"))
        )
    
    def get_job_logs(self, job_id: str, tail_lines: int = 100) -> str:
        # Query Cloud Logging (simplified)
        return "Logs available in Google Cloud Logging console"
    
    def terminate_job(self, job_id: str) -> bool:
        resp = requests.delete(f"{self.api_endpoint}/{job_id}", headers=self._headers())
        return resp.status_code == 200
