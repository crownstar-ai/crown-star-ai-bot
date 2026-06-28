# workflow/client/client.py – Temporal client for starting workflows
import asyncio
from temporalio.client import Client
from temporalio.service import TLSConfig
import os
from typing import Dict, Any, Optional

class TemporalClient:
    def __init__(self, config_path: str = "config/workflow/temporal.json"):
        self.config = self._load_config(config_path)
        self._client = None
    
    def _load_config(self, path):
        import json
        default = {
            "server_url": "localhost:7233",
            "namespace": "default",
            "task_queue": "crownstar-task-queue",
            "enable_tls": False
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    async def get_client(self) -> Client:
        if self._client is None:
            self._client = await Client.connect(
                self.config["server_url"],
                namespace=self.config["namespace"],
                tls=TLSConfig() if self.config["enable_tls"] else None
            )
        return self._client
    
    async def start_workflow(self, workflow_name: str, args: list, workflow_id: str = None, task_queue: str = None) -> str:
        client = await self.get_client()
        # Map workflow name to class
        from ..workflows.workflows import (
            DailyBackupWorkflow,
            WeeklyReportWorkflow,
            ModelTrainingWorkflow,
            ConversationSummaryWorkflow,
            ScheduledCleanupWorkflow,
            HealthCheckWorkflow
        )
        workflow_map = {
            "daily_backup": DailyBackupWorkflow,
            "weekly_report": WeeklyReportWorkflow,
            "model_training": ModelTrainingWorkflow,
            "conversation_summary": ConversationSummaryWorkflow,
            "scheduled_cleanup": ScheduledCleanupWorkflow,
            "health_check": HealthCheckWorkflow
        }
        wf_class = workflow_map.get(workflow_name)
        if not wf_class:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        handle = await client.start_workflow(
            wf_class.run,
            args,
            id=workflow_id or f"crownstar_{workflow_name}_{int(time.time())}",
            task_queue=task_queue or self.config["task_queue"]
        )
        return handle.id

    async def get_workflow_status(self, workflow_id: str) -> Dict:
        client = await self.get_client()
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        return {
            "workflow_id": desc.id,
            "status": desc.status.name,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
            "task_queue": desc.task_queue
        }
    
    async def list_workflows(self, query: str = "WorkflowType='CrownStar'") -> List[Dict]:
        client = await self.get_client()
        results = []
        async for workflow in client.list_workflows(query):
            results.append({
                "workflow_id": workflow.id,
                "status": workflow.status.name,
                "type": workflow.workflow_type
            })
        return results
    
    async def terminate_workflow(self, workflow_id: str, reason: str = "Terminated by user") -> bool:
        client = await self.get_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.terminate(reason)
        return True

_temporal_client = None
def get_temporal_client():
    global _temporal_client
    if _temporal_client is None:
        _temporal_client = TemporalClient()
    return _temporal_client
