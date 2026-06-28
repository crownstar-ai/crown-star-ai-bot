# workflow/worker/worker.py – Temporal worker that runs activities and workflows
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from workflow.activities.activities import (
    create_backup_activity,
    generate_report_activity,
    send_email_activity,
    run_model_training_activity,
    summarize_conversations_activity,
    cleanup_activity,
    health_check_activity
)
from workflow.workflows.workflows import (
    DailyBackupWorkflow,
    WeeklyReportWorkflow,
    ModelTrainingWorkflow,
    ConversationSummaryWorkflow,
    ScheduledCleanupWorkflow,
    HealthCheckWorkflow
)

async def main():
    client = await Client.connect("localhost:7233", namespace="default")
    worker = Worker(
        client,
        task_queue="crownstar-task-queue",
        workflows=[
            DailyBackupWorkflow,
            WeeklyReportWorkflow,
            ModelTrainingWorkflow,
            ConversationSummaryWorkflow,
            ScheduledCleanupWorkflow,
            HealthCheckWorkflow
        ],
        activities=[
            create_backup_activity,
            generate_report_activity,
            send_email_activity,
            run_model_training_activity,
            summarize_conversations_activity,
            cleanup_activity,
            health_check_activity
        ],
    )
    print("CrownStar Temporal worker started, listening on task queue: crownstar-task-queue")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
