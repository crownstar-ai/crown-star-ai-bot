# enterprise/distributed_worker.py – Background task worker for large jobs
import asyncio
import json
import time
import redis
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
WORKER_ID = os.environ.get("WORKER_ID", f"worker-{os.getpid()}")

class DistributedWorker:
    def __init__(self):
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self.core = create_core()
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def process_job(self, job_id: str, job_data: Dict[str, Any]):
        query = job_data.get("query", "")
        modules = job_data.get("modules", {})
        tier = job_data.get("tier", "free_pay_per_use")
        
        for mod, enabled in modules.items():
            self.core.set_module(mod, enabled)
        self.core.set_tier(tier)
        
        result = self.core.answer(query)
        
        # Store result in Redis
        self.redis_client.hset(f"job:{job_id}", mapping={
            "status": "completed",
            "result": json.dumps(result),
            "completed_at": time.time()
        })
        self.redis_client.expire(f"job:{job_id}", 3600)
        
        # Log completion
        print(f"Worker {WORKER_ID} completed job {job_id}")
    
    async def run(self):
        print(f"Worker {WORKER_ID} started, listening for jobs...")
        while self.running:
            # Pop job from queue
            job_data = self.redis_client.lpop("job_queue")
            if job_data:
                job = json.loads(job_data)
                job_id = job.get("job_id")
                await self.process_job(job_id, job)
            else:
                await asyncio.sleep(1)
    
    def stop(self):
        self.running = False
        self.executor.shutdown()

if __name__ == "__main__":
    worker = DistributedWorker()
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        worker.stop()
        print("Worker stopped")
