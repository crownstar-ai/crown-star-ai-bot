# workflow/workflows/workflows.py – Temporal workflows for CrownStar
from temporalio import workflow
from datetime import timedelta
from typing import List, Dict, Optional
import asyncio

# Import activity interfaces (will be replaced by actual activities at runtime)
with workflow.unsafe.imports_passed_through():
    from ..activities.activities import (
        create_backup_activity,
        generate_report_activity,
        send_email_activity,
        run_model_training_activity,
        summarize_conversations_activity,
        cleanup_activity,
        health_check_activity
    )

@workflow.defn
class DailyBackupWorkflow:
    """Workflow: Create daily backup and send notification"""
    @workflow.run
    async def run(self, backup_type: str = "full", email_recipients: List[str] = None) -> Dict:
        # Create backup
        backup_result = await workflow.execute_activity(
            create_backup_activity,
            args=[backup_type],
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy={"maximum_attempts": 3}
        )
        # Send email notification
        if email_recipients:
            subject = f"CrownStar Backup: {backup_result.get('backup_name', 'completed')}"
            body = f"Backup completed successfully.\nSize: {backup_result.get('size_mb', 0)} MB"
            await workflow.execute_activity(
                send_email_activity,
                args=[email_recipients, subject, body],
                start_to_close_timeout=timedelta(minutes=5)
            )
        return backup_result

@workflow.defn
class WeeklyReportWorkflow:
    """Workflow: Generate weekly analytics report and email"""
    @workflow.run
    async def run(self, report_type: str, start_date: str, end_date: str, recipients: List[str]) -> Dict:
        # Generate report
        report = await workflow.execute_activity(
            generate_report_activity,
            args=[report_type, start_date, end_date, "json"],
            start_to_close_timeout=timedelta(minutes=15)
        )
        if not report.get("success"):
            # Send failure alert
            await workflow.execute_activity(
                send_email_activity,
                args=[recipients, f"CrownStar Report Failed: {report_type}", f"Error: {report.get('error')}"],
                start_to_close_timeout=timedelta(minutes=5)
            )
            return report
        # Send email with report summary
        summary = f"Report {report_type} for period {start_date} to {end_date} generated successfully."
        await workflow.execute_activity(
            send_email_activity,
            args=[recipients, f"CrownStar Report: {report_type}", summary],
            start_to_close_timeout=timedelta(minutes=5)
        )
        return report

@workflow.defn
class ModelTrainingWorkflow:
    """Workflow: Fine‑tune a model and notify on completion"""
    @workflow.run
    async def run(self, model_name: str, dataset_path: str, hyperparams: Dict, notify_email: str) -> Dict:
        # Start training job
        training_job = await workflow.execute_activity(
            run_model_training_activity,
            args=[model_name, dataset_path, hyperparams],
            start_to_close_timeout=timedelta(minutes=10)
        )
        if not training_job.get("success"):
            await workflow.execute_activity(
                send_email_activity,
                args=[[notify_email], "Model Training Failed", f"Training for {model_name} failed: {training_job.get('error')}"],
                start_to_close_timeout=timedelta(minutes=5)
            )
            return training_job
        # Wait for job completion (simplified – would poll status)
        job_id = training_job["job_id"]
        await workflow.sleep(5)  # simulate wait
        # Notify success
        await workflow.execute_activity(
            send_email_activity,
            args=[[notify_email], f"Model Training Complete: {model_name}", f"Job ID: {job_id}. Adapter available in registry."],
            start_to_close_timeout=timedelta(minutes=5)
        )
        return training_job

@workflow.defn
class ConversationSummaryWorkflow:
    """Workflow: Summarise a user's conversations and email the summary"""
    @workflow.run
    async def run(self, user_id: str, email: str, limit: int = 100) -> Dict:
        # Get summary
        result = await workflow.execute_activity(
            summarize_conversations_activity,
            args=[user_id, limit],
            start_to_close_timeout=timedelta(minutes=5)
        )
        if result.get("success"):
            # Send email with summary
            await workflow.execute_activity(
                send_email_activity,
                args=[[email], f"Your CrownStar Conversation Summary", result.get("summary", "No summary generated")],
                start_to_close_timeout=timedelta(minutes=5)
            )
        return result

@workflow.defn
class ScheduledCleanupWorkflow:
    """Workflow: Run cleanup tasks (retention, temp files, logs)"""
    @workflow.run
    async def run(self, retention_days: int = 30, dry_run: bool = False) -> Dict:
        result = await workflow.execute_activity(
            cleanup_activity,
            args=[retention_days],
            start_to_close_timeout=timedelta(hours=2)
        )
        return result

@workflow.defn
class HealthCheckWorkflow:
    """Workflow: Periodic health check with escalation"""
    @workflow.run
    async def run(self, failure_threshold: int = 3) -> Dict:
        failures = 0
        for i in range(5):
            result = await workflow.execute_activity(
                health_check_activity,
                start_to_close_timeout=timedelta(seconds=10)
            )
            if not result["success"]:
                failures += 1
                if failures >= failure_threshold:
                    await workflow.execute_activity(
                        send_email_activity,
                        args=[["admin@crownstar.ai"], "CrownStar Health Alert", f"Service unhealthy after {failures} failures"],
                        start_to_close_timeout=timedelta(minutes=5)
                    )
                    return {"status": "unhealthy", "failures": failures}
            await workflow.sleep(10)
        return {"status": "healthy", "failures": failures}
