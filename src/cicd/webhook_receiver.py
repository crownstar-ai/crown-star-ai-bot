# cicd/webhook_receiver.py – Receive CI/CD webhooks (GitHub, GitLab)
from fastapi import APIRouter, Request, HTTPException
import hmac
import hashlib
import os
import json
from datetime import datetime
from typing import Dict

router = APIRouter(prefix="/v1/cicd", tags=["CI/CD"])

GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITLAB_WEBHOOK_SECRET = os.environ.get("GITLAB_WEBHOOK_SECRET", "")

def verify_github_signature(payload: bytes, signature: str) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        return True
    expected = "sha256=" + hmac.new(GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/webhook/github")
async def github_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_github_signature(body, signature):
        raise HTTPException(401, "Invalid signature")
    event = request.headers.get("X-GitHub-Event", "ping")
    payload = json.loads(body)
    if event == "push":
        ref = payload.get("ref", "")
        if ref == "refs/heads/main":
            # Trigger deployment (could call ArgoCD API)
            print(f"Push to main – triggering deployment")
    elif event == "deployment_status":
        # Update internal tracking
        pass
    return {"status": "received", "event": event}

@router.post("/webhook/gitlab")
async def gitlab_webhook(request: Request):
    token = request.headers.get("X-Gitlab-Token", "")
    if GITLAB_WEBHOOK_SECRET and token != GITLAB_WEBHOOK_SECRET:
        raise HTTPException(401, "Invalid token")
    body = await request.json()
    event = body.get("object_kind", "unknown")
    print(f"GitLab webhook: {event}")
    return {"status": "ok"}

@router.get("/status")
async def cicd_status():
    # Return latest deployment status (could query ArgoCD)
    return {
        "status": "operational",
        "last_deployment": datetime.utcnow().isoformat(),
        "git_commit": os.environ.get("GIT_COMMIT", "unknown")
    }
