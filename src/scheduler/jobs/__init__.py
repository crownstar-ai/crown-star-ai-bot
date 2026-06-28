# scheduler/jobs/daily_report.py – Generate daily analytics report
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from analytics.analytics_service import get_analytics_service
from email.email_service import get_email_service, EmailMessage
from datetime import datetime, timedelta
import json

def run_daily_report():
    print("Running daily analytics report...")
    analytics = get_analytics_service()
    end = datetime.utcnow()
    start = end - timedelta(days=1)
    summary = analytics.get_usage_summary(start.date().isoformat(), end.date().isoformat())
    # Send email (if configured)
    email = get_email_service()
    email.send(EmailMessage(
        to=["admin@crownstar.ai"],
        subject=f"CrownStar Daily Report – {start.date()}",
        template_name="daily_digest",
        template_data={"date": start.date().isoformat(), "items": [
            {"title": "Total Requests", "summary": summary["total_requests"]},
            {"title": "Total Cost", "summary": f"${summary['total_cost']:.2f}"},
            {"title": "Avg Latency", "summary": f"{summary['avg_latency_ms']:.0f}ms"}
        ]}
    ))
    print(f"Daily report sent. Requests: {summary['total_requests']}")

# scheduler/jobs/weekly_backup.py
def run_weekly_backup():
    print("Running weekly backup...")
    import subprocess
    subprocess.run(["python", "scripts/backup_cli.py", "now"], capture_output=True)
    print("Weekly backup completed")

# scheduler/jobs/monthly_cleanup.py
def run_monthly_cleanup():
    print("Running monthly cleanup...")
    from governance.service import get_governance
    gov = get_governance()
    deleted = gov.apply_retention_policy()
    print(f"Monthly cleanup deleted {len(deleted)} files")

# scheduler/jobs/health_check.py
def run_health_check():
    print("Running health check...")
    import requests
    try:
        resp = requests.get("http://localhost:8080/v1/health", timeout=5)
        status = "healthy" if resp.status_code == 200 else "unhealthy"
        print(f"Health check: {status}")
    except Exception as e:
        print(f"Health check failed: {e}")

# scheduler/jobs/cost_check.py
def run_cost_check():
    print("Running cost anomaly check...")
    from cost.service import get_cost_monitor
    monitor = get_cost_monitor()
    # This will trigger alert if anomaly detected
    monitor._detect_anomaly(monitor._fetch_todays_cost(), datetime.utcnow().date().isoformat())
