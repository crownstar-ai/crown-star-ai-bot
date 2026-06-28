# email/api.py – REST API for sending emails and managing templates
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from .email_service import get_email_service, EmailMessage
from .queue.queue_manager import get_queue_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/email", tags=["Email"])

class SendEmailRequest(BaseModel):
    to: List[str]
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    template_name: Optional[str] = None
    template_data: Optional[Dict] = {}
    cc: Optional[List[str]] = []
    bcc: Optional[List[str]] = []
    priority: str = "normal"

class SendTemplateRequest(BaseModel):
    to: List[str]
    subject: str
    template_name: str
    template_data: Dict

@router.post("/send")
async def send_email(req: SendEmailRequest, background: BackgroundTasks, user: dict = Depends(require_permission("user"))):
    service = get_email_service()
    msg = EmailMessage(
        to=req.to,
        subject=req.subject,
        html_content=req.html_content,
        text_content=req.text_content,
        template_name=req.template_name,
        template_data=req.template_data,
        cc=req.cc,
        bcc=req.bcc,
        priority=req.priority
    )
    if background:
        background.add_task(service.send, msg)
        return {"message": "Email queued for sending"}
    else:
        result = service.send(msg)
        return result

@router.post("/send/template")
async def send_template(req: SendTemplateRequest, background: BackgroundTasks, user: dict = Depends(require_permission("user"))):
    service = get_email_service()
    result = service.send_template(req.to, req.subject, req.template_name, req.template_data)
    return result

@router.get("/templates")
async def list_templates(user: dict = Depends(require_permission("admin"))):
    import os
    templates_dir = "src/email/templates"
    files = [f.replace(".html", "") for f in os.listdir(templates_dir) if f.endswith(".html")]
    return {"templates": files}

@router.post("/queue/retry")
async def retry_failed_queue(user: dict = Depends(require_permission("admin"))):
    qm = get_queue_manager()
    qm.retry_failed()
    return {"message": "Failed emails requeued"}

@router.get("/queue/status")
async def queue_status(user: dict = Depends(require_permission("admin"))):
    qm = get_queue_manager()
    cur = qm.conn.execute("SELECT status, COUNT(*) FROM email_queue GROUP BY status")
    counts = {row[0]: row[1] for row in cur.fetchall()}
    return {"queue_status": counts}

@router.post("/webhook/sendgrid")
async def sendgrid_webhook(request: Request):
    """Receive SendGrid event webhook (bounce, open, click)"""
    payload = await request.json()
    # Process events (log to audit, update status)
    print(f"SendGrid webhook: {payload}")
    return {"status": "received"}

@router.post("/webhook/ses")
async def ses_webhook(request: Request):
    payload = await request.json()
    print(f"SES webhook: {payload}")
    return {"status": "received"}
