# bi/scheduler.py – Generate and email reports on schedule
import schedule
import time
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime, timedelta
from .service import get_bi_service

class ReportScheduler:
    def __init__(self, smtp_config: dict = None):
        self.smtp_config = smtp_config or {}
        self.service = get_bi_service()
        self.running = False
        self.thread = None
    
    def generate_daily_report(self):
        end = datetime.utcnow().date()
        start = end - timedelta(days=1)
        output_path = f"data/bi/exports/daily_report_{start.isoformat()}.xlsx"
        self.service.export_excel(start.isoformat(), end.isoformat(), output_path)
        self._send_report(output_path, f"CrownStar Daily Report {start} to {end}")
        return output_path
    
    def generate_weekly_report(self):
        end = datetime.utcnow().date()
        start = end - timedelta(days=7)
        output_path = f"data/bi/exports/weekly_report_{start.isoformat()}.xlsx"
        self.service.export_excel(start.isoformat(), end.isoformat(), output_path)
        self._send_report(output_path, f"CrownStar Weekly Report {start} to {end}")
        return output_path
    
    def generate_monthly_report(self):
        end = datetime.utcnow().date()
        start = end.replace(day=1)
        output_path = f"data/bi/exports/monthly_report_{start.isoformat()}.xlsx"
        self.service.export_excel(start.isoformat(), end.isoformat(), output_path)
        self._send_report(output_path, f"CrownStar Monthly Report {start} to {end}")
        return output_path
    
    def _send_report(self, file_path: str, subject: str):
        if not self.smtp_config.get('enabled'):
            print(f"Report generated: {file_path}")
            return
        msg = MIMEMultipart()
        msg['From'] = self.smtp_config.get('from', 'reports@crownstar.ai')
        msg['To'] = self.smtp_config.get('to', 'admin@crownstar.ai')
        msg['Subject'] = subject
        body = "Please find attached the CrownStar report."
        msg.attach(MIMEText(body, 'plain'))
        with open(file_path, "rb") as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
            msg.attach(part)
        try:
            server = smtplib.SMTP(self.smtp_config.get('host', 'localhost'), self.smtp_config.get('port', 25))
            if self.smtp_config.get('tls'):
                server.starttls()
            if self.smtp_config.get('user'):
                server.login(self.smtp_config['user'], self.smtp_config['password'])
            server.send_message(msg)
            server.quit()
            print(f"Report sent: {subject}")
        except Exception as e:
            print(f"Failed to send email: {e}")
    
    def start_scheduler(self):
        schedule.every().day.at("06:00").do(self.generate_daily_report)
        schedule.every().monday.at("07:00").do(self.generate_weekly_report)
        schedule.every().day.at("08:00").do(self.check_monthly)
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def check_monthly(self):
        if datetime.utcnow().day == 1:
            self.generate_monthly_report()
    
    def _run(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)

_bi_scheduler = None
def get_bi_scheduler():
    global _bi_scheduler
    if _bi_scheduler is None:
        _bi_scheduler = ReportScheduler()
    return _bi_scheduler
