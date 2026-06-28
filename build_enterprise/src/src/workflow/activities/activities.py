# workflow/activities/activities.py – Temporal activities for CrownStar
import asyncio
import subprocess
import requests
import json
import time
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("crownstar.temporal.activities")

async def create_backup_activity(backup_type: str = "full", source: str = "data") -> Dict:
    """Activity: Create a backup of CrownStar data"""
    try:
        # Call existing backup service API
        resp = requests.post("http://localhost:8080/v1/backup/create", json={"backup_type": backup_type, "source": source}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"Backup created: {data.get('backup_name')}")
            return {"success": True, "backup_name": data.get("backup_name"), "size_mb": data.get("size_mb", 0)}
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.error(f"Backup activity failed: {e}")
        return {"success": False, "error": str(e)}

async def generate_report_activity(report_type: str, start_date: str, end_date: str, format: str = "json") -> Dict:
    """Activity: Generate a report (analytics, cost, etc.)"""
    try:
        # Call analytics API
        resp = requests.post("http://localhost:8080/v1/analytics/report", json={
            "start_date": start_date,
            "end_date": end_date,
            "format": format,
            "report_type": report_type
        }, timeout=60)
        if resp.status_code == 200:
            return {"success": True, "report": resp.json()}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def send_email_activity(to: List[str], subject: str, body: str, template: Optional[str] = None) -> Dict:
    """Activity: Send email via CrownStar email service"""
    try:
        payload = {"to": to, "subject": subject}
        if template:
            payload["template_name"] = template
            payload["template_data"] = {"body": body}
        else:
            payload["html_content"] = body
        resp = requests.post("http://localhost:8080/v1/email/send", json=payload, timeout=30)
        return {"success": resp.status_code == 200}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def run_model_training_activity(model_name: str, dataset_path: str, hyperparams: Dict) -> Dict:
    """Activity: Trigger model fine‑tuning"""
    try:
        resp = requests.post("http://localhost:8080/v1/finetune/train", json={
            "base_model": model_name,
            "dataset_path": dataset_path,
            "hyperparams": hyperparams
        }, timeout=10)
        if resp.status_code == 200:
            return {"success": True, "job_id": resp.json().get("job_id")}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def summarize_conversations_activity(user_id: str, limit: int = 100) -> Dict:
    """Activity: Summarise recent conversations for a user"""
    try:
        # Get conversations from memory
        resp = requests.get(f"http://localhost:8080/v1/analytics/conversations?user_id={user_id}&limit={limit}", timeout=30)
        if resp.status_code != 200:
            return {"success": False, "error": "Failed to fetch conversations"}
        convs = resp.json().get("conversations", [])
        # Build text for summarisation
        text = "\n".join([f"User: {c['user']}\nAssistant: {c['assistant']}" for c in convs])
        # Call NLP summarisation API
        summary_resp = requests.post("http://localhost:8080/v1/nlp/summarize", json={"text": text, "max_length": 200}, timeout=60)
        if summary_resp.status_code == 200:
            summary = summary_resp.json().get("summary", "")
            return {"success": True, "summary": summary, "conversations_count": len(convs)}
        return {"success": False, "error": "Summarisation failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def cleanup_activity(retention_days: int = 30) -> Dict:
    """Activity: Run cleanup (logs, old backups, temporary files)"""
    try:
        # Call governance retention API
        resp = requests.post("http://localhost:8080/v1/analytics/retention/apply", timeout=60)
        if resp.status_code == 200:
            return {"success": True, "deleted": resp.json().get("deleted_count", 0)}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def health_check_activity() -> Dict:
    """Activity: Perform health check on CrownStar services"""
    try:
        resp = requests.get("http://localhost:8080/v1/health", timeout=5)
        return {"success": resp.status_code == 200, "status": "healthy" if resp.status_code == 200 else "unhealthy"}
    except:
        return {"success": False, "status": "unreachable"}
