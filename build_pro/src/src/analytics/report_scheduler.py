# analytics/report_scheduler.py – Scheduled report generation and email delivery
import schedule
import time
import threading
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

class ReportScheduler:
    def __init__(self, analytics_service, report_generator, smtp_config=None):
        self.analytics = analytics_service
        self.report_gen = report_generator
        self.smtp_config = smtp_config or {}
        self.running = False
        self.thread = None
    
    def start(self):
        self.running = True
        # Schedule daily aggregate update at 1 AM
        schedule.every().day.at("01:00").do(self.update_daily_aggregates)
        # Schedule weekly report every Monday at 8 AM
        schedule.every().monday.at("08:00").do(self.send_weekly_report)
        # Schedule monthly report on 1st at 9 AM
        schedule.every().day.at("09:00").do(self.check_monthly_report)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    
    def _run(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)
    
    def stop(self):
        self.running = False
    
    def update_daily_aggregates(self):
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        self.analytics.update_daily_aggregates(yesterday)
        print(f"Daily aggregates updated for {yesterday}")
    
    def send_weekly_report(self):
        end = datetime.utcnow().date()
        start = end - timedelta(days=7)
        csv_content = self.report_gen.generate_csv(start.isoformat(), end.isoformat())
        self._send_email(
            subject=f"CrownStar Weekly Report {start} to {end}",
            body="Attached is your weekly usage report.",
            attachment=(csv_content, "report.csv", "text/csv")
        )
    
    def check_monthly_report(self):
        today = datetime.utcnow().date()
        if today.day == 1:
            end = today - timedelta(days=1)
            start = end.replace(day=1)
            self.send_monthly_report(start, end)
    
    def send_monthly_report(self, start_date, end_date):
        html = self.report_gen.generate_html_summary(start_date.isoformat(), end_date.isoformat())
        self._send_email(
            subject=f"CrownStar Monthly Report {start_date} to {end_date}",
            body=html,
            html=True
        )
    
    def _send_email(self, subject, body, attachment=None, html=False):
        if not self.smtp_config.get('enabled', False):
            print(f"Email disabled. Would send: {subject}")
            return
        msg = MIMEMultipart()
        msg['From'] = self.smtp_config.get('from', 'reports@crownstar.ai')
        msg['To'] = self.smtp_config.get('to', 'admin@crownstar.ai')
        msg['Subject'] = subject
        if html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        if attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment[0].encode('utf-8'))
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={attachment[1]}')
            msg.attach(part)
        try:
            server = smtplib.SMTP(self.smtp_config.get('host', 'localhost'), self.smtp_config.get('port', 25))
            if self.smtp_config.get('tls', False):
                server.starttls()
            if self.smtp_config.get('user'):
                server.login(self.smtp_config['user'], self.smtp_config['password'])
            server.send_message(msg)
            server.quit()
            print(f"Email sent: {subject}")
        except Exception as e:
            print(f"Email failed: {e}")
