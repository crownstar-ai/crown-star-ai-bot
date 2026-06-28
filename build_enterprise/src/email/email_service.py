# email/email_service.py – Unified email service with multiple providers
import os
import json
import asyncio
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import queue
import time

@dataclass
class EmailMessage:
    to: List[str]
    subject: str
    html_content: str = ""
    text_content: str = ""
    from_email: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    attachments: List[Dict] = field(default_factory=list)  # [{"filename": "file.pdf", "content": bytes, "mime": "application/pdf"}]
    template_name: Optional[str] = None
    template_data: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    priority: str = "normal"  # high, normal, low

class EmailProvider:
    def send(self, message: EmailMessage) -> Dict:
        raise NotImplementedError

class SendGridProvider(EmailProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    def send(self, message: EmailMessage) -> Dict:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            sg = SendGridAPIClient(self.api_key)
            mail = Mail(
                from_email=message.from_email,
                to_emails=message.to,
                subject=message.subject,
                html_content=message.html_content,
                plain_text_content=message.text_content
            )
            response = sg.send(mail)
            return {"success": response.status_code in (200, 202), "message_id": response.headers.get("X-Message-Id"), "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

class SESProvider(EmailProvider):
    def __init__(self, region: str = "us-east-1", access_key: str = None, secret_key: str = None):
        self.region = region
        self.access_key = access_key or os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
    def send(self, message: EmailMessage) -> Dict:
        try:
            import boto3
            client = boto3.client('ses', region_name=self.region, aws_access_key_id=self.access_key, aws_secret_access_key=self.secret_key)
            response = client.send_email(
                Source=message.from_email,
                Destination={'ToAddresses': message.to},
                Message={
                    'Subject': {'Data': message.subject},
                    'Body': {'Html': {'Data': message.html_content}, 'Text': {'Data': message.text_content or message.html_content}}
                }
            )
            return {"success": True, "message_id": response.get("MessageId")}
        except Exception as e:
            return {"success": False, "error": str(e)}

class SMTPProvider(EmailProvider):
    def __init__(self, host: str, port: int = 587, username: str = None, password: str = None, use_tls: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
    def send(self, message: EmailMessage) -> Dict:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = message.from_email
            msg["To"] = ", ".join(message.to)
            if message.cc:
                msg["Cc"] = ", ".join(message.cc)
            if message.reply_to:
                msg["Reply-To"] = message.reply_to
            if message.text_content:
                msg.attach(MIMEText(message.text_content, "plain"))
            if message.html_content:
                msg.attach(MIMEText(message.html_content, "html"))
            with smtplib.SMTP(self.host, self.port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(msg)
            return {"success": True, "message_id": f"smtp-{int(time.time())}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

class MailgunProvider(EmailProvider):
    def __init__(self, domain: str, api_key: str):
        self.domain = domain
        self.api_key = api_key
    def send(self, message: EmailMessage) -> Dict:
        try:
            import requests
            auth = ("api", self.api_key)
            data = {
                "from": message.from_email,
                "to": ",".join(message.to),
                "subject": message.subject,
                "html": message.html_content,
                "text": message.text_content
            }
            resp = requests.post(f"https://api.mailgun.net/v3/{self.domain}/messages", auth=auth, data=data)
            return {"success": resp.status_code == 200, "message_id": resp.json().get("id"), "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

class ResendProvider(EmailProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    def send(self, message: EmailMessage) -> Dict:
        try:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            data = {
                "from": message.from_email,
                "to": message.to,
                "subject": message.subject,
                "html": message.html_content,
                "text": message.text_content
            }
            resp = requests.post("https://api.resend.com/emails", headers=headers, json=data)
            return {"success": resp.status_code == 200, "message_id": resp.json().get("id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

def get_provider(provider_name: str, config: dict) -> EmailProvider:
    if provider_name == "sendgrid":
        return SendGridProvider(config["api_key"])
    elif provider_name == "ses":
        return SESProvider(config.get("region", "us-east-1"), config.get("access_key"), config.get("secret_key"))
    elif provider_name == "smtp":
        return SMTPProvider(config["host"], config["port"], config.get("username"), config.get("password"), config.get("use_tls", True))
    elif provider_name == "mailgun":
        return MailgunProvider(config["domain"], config["api_key"])
    elif provider_name == "resend":
        return ResendProvider(config["api_key"])
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

class EmailService:
    def __init__(self, config_path: str = "config/email/config.json"):
        self.config = self._load_config(config_path)
        self.provider = get_provider(self.config["provider"], self.config[self.config["provider"]])
        self.queue = queue.Queue()
        self._start_worker()
    
    def _load_config(self, path):
        default = {
            "provider": "smtp",
            "smtp": {"host": "localhost", "port": 25, "use_tls": False},
            "sendgrid": {"api_key": ""},
            "ses": {"region": "us-east-1"},
            "mailgun": {"domain": "", "api_key": ""},
            "resend": {"api_key": ""},
            "default_from": "noreply@crownstar.ai",
            "queue_enabled": True,
            "async_send": True,
            "rate_limit_per_minute": 60,
            "retry_attempts": 3
        }
        if Path(path).exists():
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _start_worker(self):
        if not self.config["async_send"]:
            return
        def worker():
            while True:
                try:
                    msg = self.queue.get(timeout=1)
                    self._send_sync(msg)
                    self.queue.task_done()
                except:
                    pass
        threading.Thread(target=worker, daemon=True).start()
    
    def _send_sync(self, message: EmailMessage) -> Dict:
        if not message.from_email:
            message.from_email = self.config["default_from"]
        # Render template if needed
        if message.template_name:
            template = self._render_template(message.template_name, message.template_data)
            message.html_content = template.get("html", "")
            message.text_content = template.get("text", "")
        return self.provider.send(message)
    
    def _render_template(self, template_name: str, data: Dict) -> Dict:
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader("src/email/templates"))
            template = env.get_template(f"{template_name}.html")
            html = template.render(**data)
            text_template = env.get_template(f"{template_name}.txt")
            text = text_template.render(**data) if text_template else ""
            return {"html": html, "text": text}
        except ImportError:
            return {"html": f"<html><body><h1>{template_name}</h1><pre>{json.dumps(data, indent=2)}</pre></body></html>", "text": ""}
    
    def send(self, message: EmailMessage) -> Dict:
        if self.config["async_send"]:
            self.queue.put(message)
            return {"success": True, "queued": True, "message": "Queued for delivery"}
        else:
            return self._send_sync(message)
    
    def send_template(self, to: List[str], subject: str, template_name: str, template_data: Dict, **kwargs) -> Dict:
        msg = EmailMessage(
            to=to,
            subject=subject,
            template_name=template_name,
            template_data=template_data,
            **kwargs
        )
        return self.send(msg)

_email_service = None
def get_email_service():
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
