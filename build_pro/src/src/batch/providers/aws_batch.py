# batch/providers/aws_batch.py – AWS Batch integration
import os
import boto3
from typing import Dict, List, Optional
from datetime import datetime
from .base import BatchProvider, BatchJob

class AWSBatchProvider(BatchProvider):
    def __init__(self, region: str = "us-east-1", job_queue: str = "crownstar-queue", job_definition: str = "crownstar-job"):
        self.region = region
        self.job_queue = job_queue
        self.job_definition = job_definition
        self.client = boto3.client('batch', region_name=region)
    
    def submit_job(self, job_name: str, command: List[str], environment: Dict = None, resources: Dict = None) -> str:
        params = {
            "jobName": job_name,
            "jobQueue": self.job_queue,
            "jobDefinition": self.job_definition,
            "containerOverrides": {
                "command": command,
                "environment": [{"name": k, "value": v} for k, v in (environment or {}).items()]
            }
        }
        if resources:
            if "vcpus" in resources:
                params["containerOverrides"]["vcpus"] = resources["vcpus"]
            if "memory" in resources:
                params["containerOverrides"]["memory"] = resources["memory"]
        resp = self.client.submit_job(**params)
        return resp["jobId"]
    
    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        jobs = []
        next_token = None
        while len(jobs) < limit:
            params = {"jobQueue": self.job_queue, "maxResults": min(100, limit - len(jobs))}
            if next_token:
                params["nextToken"] = next_token
            resp = self.client.list_jobs(**params)
            for job in resp.get("jobSummaryList", []):
                jobs.append(BatchJob(
                    job_id=job["jobId"],
                    name=job["jobName"],
                    status=job["status"],
                    created_at=job["createdAt"],
                    started_at=job.get("startedAt"),
                    completed_at=job.get("stoppedAt")
                ))
            next_token = resp.get("nextToken")
            if not next_token:
                break
        return jobs[:limit]
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        resp = self.client.describe_jobs(jobs=[job_id])
        jobs = resp.get("jobs", [])
        if not jobs:
            return None
        job = jobs[0]
        return BatchJob(
            job_id=job["jobId"],
            name=job["jobName"],
            status=job["status"],
            created_at=job["createdAt"],
            started_at=job.get("startedAt"),
            completed_at=job.get("stoppedAt")
        )
    
    def get_job_logs(self, job_id: str, tail_lines: int = 100) -> str:
        # Use CloudWatch Logs if enabled
        logs = self.client.describe_jobs(jobs=[job_id])
        log_group = logs["jobs"][0].get("container", {}).get("logStreamName")
        if not log_group:
            return "Logs not available"
        logs_client = boto3.client('logs', region_name=self.region)
        try:
            resp = logs_client.get_log_events(
                logGroupName="/aws/batch/job",
                logStreamName=log_group,
                limit=tail_lines
            )
            return "\n".join([e["message"] for e in resp.get("events", [])])
        except:
            return "Failed to retrieve logs"
    
    def terminate_job(self, job_id: str) -> bool:
        try:
            self.client.terminate_job(jobId=job_id, reason="Terminated by user")
            return True
        except:
            return False
