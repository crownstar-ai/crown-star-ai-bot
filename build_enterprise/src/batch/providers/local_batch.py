# batch/providers/local_batch.py – Local subprocess simulation
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json
from .base import BatchProvider, BatchJob

class LocalBatchProvider(BatchProvider):
    def __init__(self, work_dir: str = "data/batch"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.jobs = {}
        self._lock = threading.Lock()
    
    def _run_job(self, job_id: str, command: List[str], env: Dict):
        with self._lock:
            job = self.jobs[job_id]
            job.status = "running"
            job.started_at = datetime.utcnow()
        output_file = self.work_dir / f"{job_id}.out"
        error_file = self.work_dir / f"{job_id}.err"
        try:
            result = subprocess.run(
                command,
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                timeout=3600
            )
            output = result.stdout + "\n" + result.stderr
            output_file.write_text(output)
            with self._lock:
                job.status = "succeeded" if result.returncode == 0 else "failed"
                job.completed_at = datetime.utcnow()
                job.output = output[:5000]
        except Exception as e:
            error_file.write_text(str(e))
            with self._lock:
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.output = str(e)
    
    def submit_job(self, job_name: str, command: List[str], environment: Dict = None, resources: Dict = None) -> str:
        job_id = str(uuid.uuid4())[:8]
        with self._lock:
            self.jobs[job_id] = BatchJob(
                job_id=job_id,
                name=job_name,
                status="pending",
                created_at=datetime.utcnow(),
                output=""
            )
        thread = threading.Thread(target=self._run_job, args=(job_id, command, environment or {}), daemon=True)
        thread.start()
        return job_id
    
    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        with self._lock:
            return list(self.jobs.values())[-limit:]
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        with self._lock:
            return self.jobs.get(job_id)
    
    def get_job_logs(self, job_id: str, tail_lines: int = 100) -> str:
        with self._lock:
            job = self.jobs.get(job_id)
            if job and job.output:
                lines = job.output.splitlines()
                return "\n".join(lines[-tail_lines:])
        return "No logs available"
    
    def terminate_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self.jobs:
                self.jobs[job_id].status = "terminated"
                return True
        return False
