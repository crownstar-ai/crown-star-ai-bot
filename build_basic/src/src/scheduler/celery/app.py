# scheduler/celery/app.py – Celery application setup
import os
from celery import Celery

# Celery configuration
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

app = Celery(
    "crownstar",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "scheduler.celery.tasks.analytics",
        "scheduler.celery.tasks.backup",
        "scheduler.celery.tasks.email",
        "scheduler.celery.tasks.cleanup"
    ]
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

# scheduler/celery/tasks/analytics.py
def analytics_tasks():
    from celery import shared_task
    @shared_task(name="generate_daily_report")
    def generate_daily_report():
        from ..jobs.daily_report import run_daily_report
        return run_daily_report()
    @shared_task(name="generate_weekly_report")
    def generate_weekly_report():
        from ..jobs.weekly_backup import run_weekly_backup
        return run_weekly_backup()
    return locals()

# scheduler/celery/beat_schedule.py
beat_schedule = {
    "daily-report": {
        "task": "generate_daily_report",
        "schedule": 86400.0,  # 24 hours
        "options": {"expires": 43200}
    },
    "weekly-backup": {
        "task": "generate_weekly_report",
        "schedule": 604800.0,  # 7 days
        "options": {"expires": 86400}
    }
}
