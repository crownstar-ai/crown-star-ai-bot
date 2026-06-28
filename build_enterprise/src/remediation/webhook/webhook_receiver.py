# remediation/webhook/webhook_receiver.py – Receive alerts from external systems
from fastapi import APIRouter, Request, HTTPException
import json
import logging
from ..engine.engine import get_remediation_engine

logger = logging.getLogger("crownstar.remediation.webhook")
router = APIRouter(prefix="/v1/remediation/webhook", tags=["Remediation Webhook"])

@router.post("/prometheus")
async def prometheus_webhook(request: Request):
    """Receive Alertmanager webhook from Prometheus"""
    payload = await request.json()
    logger.info(f"Received Prometheus alert: {json.dumps(payload)[:200]}")
    # Process alerts and trigger remediation if needed
    engine = get_remediation_engine()
    # Example: map alertname to condition
    for alert in payload.get("alerts", []):
        alertname = alert.get("labels", {}).get("alertname")
        status = alert.get("status")
        if status == "firing":
            # Manually trigger evaluation? Or use synthetic condition
            # For simplicity, add to context via event
            # Here we could trigger remediation immediately
            if alertname == "HighErrorRate":
                # Force run remediation (policy id: rollback_on_error_spike)
                # Evaluate only that policy? For now, let periodic handle it.
                pass
    return {"status": "received"}

@router.post("/datadog")
async def datadog_webhook(request: Request):
    payload = await request.json()
    logger.info(f"Received Datadog alert: {json.dumps(payload)[:200]}")
    return {"status": "received"}

@router.post("/cloudwatch")
async def cloudwatch_webhook(request: Request):
    payload = await request.json()
    logger.info(f"Received CloudWatch alarm: {json.dumps(payload)[:200]}")
    return {"status": "received"}

@router.post("/generic")
async def generic_webhook(request: Request):
    payload = await request.json()
    # Generic webhook – can be used to trigger remediation on demand
    trigger_policy = payload.get("policy_id")
    if trigger_policy:
        engine = get_remediation_engine()
        # Force evaluation for specific policy (simplified: run all, but we can add targeted later)
        engine.evaluate_and_remediate()
    return {"status": "received"}
