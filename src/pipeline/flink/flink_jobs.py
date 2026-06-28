# pipeline/flink/flink_jobs.py – Flink job submission (via REST API)
import requests
import json
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("crownstar.pipeline.flink")

class FlinkJobManager:
    def __init__(self, rest_url: str = "http://localhost:8081"):
        self.rest_url = rest_url
        self.jobs = {}
    
    def submit_sql_job(self, sql_statement: str, job_name: str = "crownstar_sql_job") -> Optional[str]:
        """Submit SQL job via Flink SQL Gateway (stub)"""
        # In real impl, would use Flink SQL Gateway REST API
        logger.info(f"Submitting SQL job: {job_name}")
        # Placeholder – return dummy job ID
        job_id = f"flink_sql_{hash(job_name)}"
        self.jobs[job_id] = {"name": job_name, "status": "running", "sql": sql_statement}
        return job_id
    
    def submit_jar_job(self, jar_path: str, main_class: str, args: List[str] = None) -> Optional[str]:
        """Submit pre‑built JAR job via Flink REST API"""
        # This would upload JAR and submit
        logger.info(f"Submitting JAR job: {jar_path} main={main_class}")
        job_id = f"flink_jar_{int(time.time())}"
        self.jobs[job_id] = {"name": jar_path, "status": "running"}
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        return self.jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "cancelled"
            return True
        return False
    
    def list_jobs(self) -> List[Dict]:
        return [{"job_id": jid, **info} for jid, info in self.jobs.items()]

_flink = None
def get_flink_job_manager():
    global _flink
    if _flink is None:
        _flink = FlinkJobManager()
    return _flink

# Example Flink SQL for CrownStar
EXAMPLE_FLINK_SQL = '''
CREATE TABLE crownstar_events (
    event_id STRING,
    event_type STRING,
    user_id STRING,
    tenant_id STRING,
    payload STRING,
    event_time TIMESTAMP(3),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'crownstar.user_actions',
    'properties.bootstrap.servers' = 'localhost:9092',
    'format' = 'json'
);

CREATE TABLE hourly_aggregates (
    window_start TIMESTAMP(3),
    tenant_id STRING,
    event_count BIGINT,
    PRIMARY KEY (window_start, tenant_id) NOT ENFORCED
) WITH (
    'connector' = 'jdbc',
    'url' = 'jdbc:postgresql://localhost:5432/crownstar',
    'table-name' = 'hourly_aggregates'
);

INSERT INTO hourly_aggregates
SELECT 
    TUMBLE_START(event_time, INTERVAL '1' HOUR) as window_start,
    tenant_id,
    COUNT(*) as event_count
FROM crownstar_events
GROUP BY TUMBLE(event_time, INTERVAL '1' HOUR), tenant_id;
'''
