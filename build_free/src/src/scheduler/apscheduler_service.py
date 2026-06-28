# scheduler/apscheduler_service.py – Advanced Python Scheduler (APScheduler)
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import pytz

class SchedulerService:
    def __init__(self, config_path: str = "config/scheduler/config.json"):
        self.config = self._load_config(config_path)
        self.scheduler = None
        self._init_scheduler()
        self._register_builtin_jobs()
    
    def _load_config(self, path):
        default = {
            "timezone": "UTC",
            "jobstores": {
                "default": {"type": "sqlalchemy", "url": "sqlite:///data/scheduler/jobs.db"}
            },
            "executors": {
                "default": {"type": "threadpool", "max_workers": 10},
                "processpool": {"type": "processpool", "max_workers": 4}
            },
            "job_defaults": {"coalesce": False, "max_instances": 3},
            "builtin_jobs": [
                {"id": "daily_analytics_report", "trigger": "cron", "hour": 6, "minute": 0, "func": "run_daily_report"},
                {"id": "weekly_backup", "trigger": "cron", "day_of_week": "sun", "hour": 2, "minute": 0, "func": "run_weekly_backup"},
                {"id": "monthly_cleanup", "trigger": "cron", "day": 1, "hour": 3, "minute": 0, "func": "run_monthly_cleanup"},
                {"id": "health_check", "trigger": "interval", "minutes": 15, "func": "run_health_check"},
                {"id": "cost_anomaly_check", "trigger": "interval", "hours": 6, "func": "run_cost_check"}
            ]
        }
        if Path(path).exists():
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _init_scheduler(self):
        jobstores = {}
        for name, store_cfg in self.config["jobstores"].items():
            if store_cfg["type"] == "sqlalchemy":
                jobstores[name] = SQLAlchemyJobStore(url=store_cfg["url"])
        executors = {
            "default": ThreadPoolExecutor(self.config["executors"]["default"]["max_workers"]),
            "processpool": ProcessPoolExecutor(self.config["executors"]["processpool"]["max_workers"])
        }
        job_defaults = self.config["job_defaults"]
        timezone = pytz.timezone(self.config["timezone"])
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=timezone
        )
        self.scheduler.start()
        print("APScheduler started")
    
    def _register_builtin_jobs(self):
        for job_cfg in self.config["builtin_jobs"]:
            if not self.get_job(job_cfg["id"]):
                self.add_job(
                    job_id=job_cfg["id"],
                    func_name=job_cfg["func"],
                    trigger_type=job_cfg["trigger"],
                    **{k:v for k,v in job_cfg.items() if k not in ["id", "func", "trigger"]}
                )
    
    def _get_func(self, func_name: str) -> Callable:
        # Resolve function by name (import dynamically)
        if func_name == "run_daily_report":
            from jobs.daily_report import run_daily_report
            return run_daily_report
        elif func_name == "run_weekly_backup":
            from jobs.weekly_backup import run_weekly_backup
            return run_weekly_backup
        elif func_name == "run_monthly_cleanup":
            from jobs.monthly_cleanup import run_monthly_cleanup
            return run_monthly_cleanup
        elif func_name == "run_health_check":
            from jobs.health_check import run_health_check
            return run_health_check
        elif func_name == "run_cost_check":
            from jobs.cost_check import run_cost_check
            return run_cost_check
        else:
            raise ValueError(f"Unknown job function: {func_name}")
    
    def add_job(self, job_id: str, func_name: str, trigger_type: str, **kwargs) -> bool:
        func = self._get_func(func_name)
        if trigger_type == "cron":
            trigger = CronTrigger(
                year=kwargs.get("year"), month=kwargs.get("month"), day=kwargs.get("day"),
                week=kwargs.get("week"), day_of_week=kwargs.get("day_of_week"),
                hour=kwargs.get("hour"), minute=kwargs.get("minute"), second=kwargs.get("second"),
                timezone=pytz.timezone(self.config["timezone"])
            )
        elif trigger_type == "interval":
            trigger = IntervalTrigger(
                weeks=kwargs.get("weeks"), days=kwargs.get("days"),
                hours=kwargs.get("hours"), minutes=kwargs.get("minutes"),
                seconds=kwargs.get("seconds")
            )
        elif trigger_type == "date":
            run_date = kwargs.get("run_date")
            if isinstance(run_date, str):
                run_date = datetime.fromisoformat(run_date)
            trigger = DateTrigger(run_date=run_date)
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")
        self.scheduler.add_job(func, trigger=trigger, id=job_id, replace_existing=True)
        print(f"Job added: {job_id}")
        return True
    
    def remove_job(self, job_id: str) -> bool:
        try:
            self.scheduler.remove_job(job_id)
            return True
        except:
            return False
    
    def pause_job(self, job_id: str) -> bool:
        try:
            self.scheduler.pause_job(job_id)
            return True
        except:
            return False
    
    def resume_job(self, job_id: str) -> bool:
        try:
            self.scheduler.resume_job(job_id)
            return True
        except:
            return False
    
    def trigger_job(self, job_id: str) -> bool:
        try:
            self.scheduler.get_job(job_id).modify(next_run_time=datetime.utcnow())
            return True
        except:
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        return {
            "id": job.id,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
            "pending": job.pending
        }
    
    def list_jobs(self) -> List[Dict]:
        jobs = self.scheduler.get_jobs()
        return [{"id": j.id, "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None, "trigger": str(j.trigger)} for j in jobs]
    
    def shutdown(self):
        self.scheduler.shutdown()

_scheduler = None
def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler
