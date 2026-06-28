# batch/providers/base.py – Abstract base for batch providers
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class BatchJob:
    job_id: str
    name: str
    status: str  # pending, running, succeeded, failed, terminated
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    log_url: Optional[str] = None
    output: Optional[str] = None

class BatchProvider(ABC):
    @abstractmethod
    def submit_job(self, job_name: str, command: List[str], environment: Dict = None, resources: Dict = None) -> str:
        """Submit a job, return job ID"""
        pass
    
    @abstractmethod
    def list_jobs(self, limit: int = 50) -> List[BatchJob]:
        pass
    
    @abstractmethod
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        pass
    
    @abstractmethod
    def get_job_logs(self, job_id: str, tail_lines: int = 100) -> str:
        pass
    
    @abstractmethod
    def terminate_job(self, job_id: str) -> bool:
        pass
