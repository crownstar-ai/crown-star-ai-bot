# batch/providers/azure_batch.py – Azure Batch integration
import os
from azure.batch import BatchServiceClient
from azure.batch.batch_auth import SharedKeyCredentials
from azure.batch.models import JobAddParameter, TaskAddParameter
from typing import List, Optional
from datetime import datetime
from .base import BatchProvider, BatchJob

class AzureBatchProvider(BatchProvider):
    def __init__(self, account_name: str, account_key: str, account_url: str, pool_id: str = "crownstar-pool"):
        self.account_name = account_name
        self.account_key = account_key
        self.account_url = account_url
        self.pool_id = pool_id
        creds = SharedKeyCredentials(account_name, account_key)
        self.client = BatchServiceClient(creds, base_url=account_url)
    
    def submit_job(self, job_name: str, command: List[str], environment: Dict = None, resources: Dict = None) -> str:
        job_id = f"crownstar-{job_name}-{int(datetime.utcnow().timestamp())}"
        job = JobAddParameter(id=job_id, pool_info={"pool_id": self.pool_id})
        self.client.job.add(job)
        task = TaskAddParameter(
            id=f"task-{job_id}",
            command_line=" ".join(command),
            environment_settings=[{"name": k, "value": v} for k, v in (environment or {}).items()]
        )
        self.client.task.add(job_id, task)
        return job_id
    
    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        jobs = self.client.job.list()
        result = []
        for job in jobs[:limit]:
            result.append(BatchJob(
                job_id=job.id,
                name=job.id,
                status=job.state.value,
                created_at=job.creation_time,
                started_at=job.last_modified if hasattr(job, "last_modified") else None
            ))
        return result
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        try:
            job = self.client.job.get(job_id)
            return BatchJob(
                job_id=job.id,
                name=job.id,
                status=job.state.value,
                created_at=job.creation_time,
                started_at=job.last_modified
            )
        except:
            return None
    
    def get_job_logs(self, job_id: str, tail_lines: int = 100) -> str:
        try:
            tasks = self.client.task.list(job_id)
            logs = []
            for task in tasks:
                node_info = self.client.task.get(job_id, task.id).node_info
                if node_info:
                    logs.append(f"Task {task.id} ran on node {node_info.node_id}")
            return "\n".join(logs) if logs else "No logs available"
        except:
            return "Failed to retrieve logs"
    
    def terminate_job(self, job_id: str) -> bool:
        try:
            self.client.job.terminate(job_id)
            return True
        except:
            return False
