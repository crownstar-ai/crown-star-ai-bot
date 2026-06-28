# finetune/service.py – Core fine‑tuning service
import os
import json
import time
import threading
import subprocess
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import uuid

class FineTuneJob:
    def __init__(self, job_id: str, base_model: str, dataset_path: str, output_dir: str, config: Dict):
        self.job_id = job_id
        self.base_model = base_model
        self.dataset_path = dataset_path
        self.output_dir = output_dir
        self.config = config
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0
        self.start_time = None
        self.end_time = None
        self.error = None

class FineTuneService:
    def __init__(self, config_path: str = "config/finetune/config.json"):
        self.config = self._load_config(config_path)
        self.jobs: Dict[str, FineTuneJob] = {}
        self._active_jobs = {}
        self._init_dirs()
    
    def _load_config(self, path):
        default = {
            "default_base_model": "deepseek-ai/DeepSeek-V2-Lite",
            "output_root": "data/finetune/adapters",
            "checkpoint_root": "data/finetune/checkpoints",
            "max_concurrent_jobs": 2,
            "default_hyperparams": {
                "num_epochs": 3,
                "batch_size": 4,
                "gradient_accumulation_steps": 4,
                "learning_rate": 2e-4,
                "max_seq_length": 512,
                "lora_r": 8,
                "lora_alpha": 16,
                "lora_dropout": 0.1,
                "use_4bit": True,
                "use_lora": True
            }
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _init_dirs(self):
        Path(self.config["output_root"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["checkpoint_root"]).mkdir(parents=True, exist_ok=True)
    
    def submit_job(self, base_model: str, dataset_path: str, hyperparams: Dict = None) -> str:
        """Submit a fine‑tuning job"""
        job_id = str(uuid.uuid4())[:8]
        output_dir = Path(self.config["output_root"]) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        params = self.config["default_hyperparams"].copy()
        if hyperparams:
            params.update(hyperparams)
        job = FineTuneJob(job_id, base_model, dataset_path, str(output_dir), params)
        self.jobs[job_id] = job
        # Start background thread if under concurrency limit
        self._maybe_start_job(job_id)
        return job_id
    
    def _maybe_start_job(self, job_id: str):
        if len(self._active_jobs) >= self.config["max_concurrent_jobs"]:
            return
        job = self.jobs.get(job_id)
        if not job or job.status != "pending":
            return
        thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        self._active_jobs[job_id] = thread
        job.status = "running"
        job.start_time = time.time()
        thread.start()
    
    def _run_job(self, job_id: str):
        job = self.jobs[job_id]
        script_path = os.path.join(os.path.dirname(__file__), "trainer", "train_script.py")
        cmd = [
            sys.executable, script_path,
            "--base_model", job.base_model,
            "--dataset_path", job.dataset_path,
            "--output_dir", job.output_dir,
            "--job_id", job_id
        ]
        for k, v in job.config.items():
            cmd.extend([f"--{k}", str(v)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=86400)  # 24h max
            if result.returncode == 0:
                job.status = "completed"
                job.progress = 1.0
            else:
                job.status = "failed"
                job.error = result.stderr
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        finally:
            job.end_time = time.time()
            del self._active_jobs[job_id]
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "status": job.status,
            "progress": job.progress,
            "base_model": job.base_model,
            "start_time": job.start_time,
            "end_time": job.end_time,
            "error": job.error
        }
    
    def list_jobs(self, limit: int = 20) -> List[Dict]:
        jobs = list(self.jobs.values())[-limit:]
        return [{
            "job_id": j.job_id,
            "status": j.status,
            "base_model": j.base_model,
            "start_time": j.start_time,
            "end_time": j.end_time
        } for j in jobs]
    
    def cancel_job(self, job_id: str) -> bool:
        # Would need to kill subprocess – simplified stub
        return False

_ft_service = None
def get_finetune_service():
    global _ft_service
    if _ft_service is None:
        _ft_service = FineTuneService()
    return _ft_service
