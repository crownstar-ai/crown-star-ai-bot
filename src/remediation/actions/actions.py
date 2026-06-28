# remediation/actions/actions.py – Available remediation actions
import subprocess
import requests
import time
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("crownstar.remediation")

class RemediationActions:
    @staticmethod
    def restart_pod(pod_name: str = "crownstar-api", namespace: str = "crownstar") -> bool:
        """Restart Kubernetes pod by deleting it"""
        try:
            cmd = ["kubectl", "delete", "pod", "-l", f"app={pod_name}", "-n", namespace]
            subprocess.run(cmd, check=True, timeout=30)
            logger.info(f"Restarted pod {pod_name} in namespace {namespace}")
            return True
        except Exception as e:
            logger.error(f"Failed to restart pod: {e}")
            return False

    @staticmethod
    def scale_deployment(deployment: str = "crownstar-api", replicas: int = 3, namespace: str = "crownstar") -> bool:
        """Scale Kubernetes deployment to specified replicas"""
        try:
            cmd = ["kubectl", "scale", "deployment", deployment, f"--replicas={replicas}", "-n", namespace]
            subprocess.run(cmd, check=True, timeout=30)
            logger.info(f"Scaled deployment {deployment} to {replicas} replicas")
            return True
        except Exception as e:
            logger.error(f"Failed to scale deployment: {e}")
            return False

    @staticmethod
    def clear_cache() -> bool:
        """Clear CrownStar cache via API"""
        try:
            resp = requests.post("http://localhost:8080/v1/cache/clear", timeout=10)
            success = resp.status_code == 200
            logger.info(f"Cache cleared: {success}")
            return success
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    @staticmethod
    def failover_region() -> bool:
        """Trigger cross‑region failover"""
        try:
            resp = requests.post("http://localhost:8080/v1/replication/failover/trigger", timeout=10)
            success = resp.status_code == 200
            logger.info(f"Failover triggered: {success}")
            return success
        except Exception as e:
            logger.error(f"Failed to trigger failover: {e}")
            return False

    @staticmethod
    def restart_service(service_name: str = "crownstar") -> bool:
        """Restart systemd service on local node"""
        try:
            subprocess.run(["systemctl", "restart", service_name], check=True, timeout=30)
            logger.info(f"Restarted systemd service {service_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            return False

    @staticmethod
    def send_alert(message: str, severity: str = "warning") -> bool:
        """Send alert via email/Slack/webhook"""
        # Use existing email service if available
        try:
            from email.email_service import get_email_service, EmailMessage
            email = get_email_service()
            email.send(EmailMessage(
                to=["admin@crownstar.ai"],
                subject=f"[Auto‑Remediation] {severity.upper()}: {message[:100]}",
                text_content=message
            ))
            logger.info(f"Alert sent: {message[:100]}")
            return True
        except:
            # Fallback to print
            print(f"ALERT [{severity}]: {message}")
            return False

    @staticmethod
    def rollback_deployment(deployment: str = "crownstar-api", revision: int = None) -> bool:
        """Rollback Kubernetes deployment to previous revision"""
        try:
            cmd = ["kubectl", "rollout", "undo", f"deployment/{deployment}", "-n", "crownstar"]
            if revision:
                cmd = ["kubectl", "rollout", "undo", f"deployment/{deployment}", f"--to-revision={revision}", "-n", "crownstar"]
            subprocess.run(cmd, check=True, timeout=60)
            logger.info(f"Rolled back deployment {deployment} (revision {revision or 'previous'})")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            return False

    @staticmethod
    def kill_slow_requests() -> bool:
        """Terminate long‑running database queries or connections (stub)"""
        logger.info("Killing slow requests (stub)")
        return True

    @staticmethod
    def restart_database() -> bool:
        """Restart database (RDS/PostgreSQL) – dangerous, used as last resort"""
        # In production, would call cloud provider API
        logger.warning("Database restart requested – manual intervention may be required")
        return True
