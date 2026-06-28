# email/queue/queue_manager.py – Persistent email queue (SQLite)
import sqlite3
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from ..email_service import EmailMessage

class EmailQueueManager:
    def __init__(self, db_path: str = "data/email/queue/email_queue.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS email_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                to_address TEXT,
                subject TEXT,
                html_content TEXT,
                text_content TEXT,
                from_email TEXT,
                cc TEXT,
                bcc TEXT,
                reply_to TEXT,
                template_name TEXT,
                template_data TEXT,
                priority TEXT,
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT,
                scheduled_at TEXT,
                sent_at TEXT
            )
        ''')
        self.conn.commit()
    
    def enqueue(self, msg: EmailMessage, scheduled_at: datetime = None) -> int:
        cur = self.conn.cursor()
        cur.execute('''
            INSERT INTO email_queue
            (to_address, subject, html_content, text_content, from_email, cc, bcc, reply_to,
             template_name, template_data, priority, created_at, scheduled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ",".join(msg.to),
            msg.subject,
            msg.html_content,
            msg.text_content,
            msg.from_email,
            ",".join(msg.cc),
            ",".join(msg.bcc),
            msg.reply_to,
            msg.template_name,
            json.dumps(msg.template_data),
            msg.priority,
            datetime.utcnow().isoformat(),
            scheduled_at.isoformat() if scheduled_at else None
        ))
        self.conn.commit()
        return cur.lastrowid
    
    def dequeue(self, limit: int = 10) -> List[dict]:
        cur = self.conn.execute('''
            SELECT id, to_address, subject, html_content, text_content, from_email, cc, bcc, reply_to,
                   template_name, template_data, priority
            FROM email_queue
            WHERE status = 'pending' AND (scheduled_at IS NULL OR scheduled_at <= ?)
            ORDER BY priority = 'high' DESC, created_at ASC
            LIMIT ?
        ''', (datetime.utcnow().isoformat(), limit))
        rows = cur.fetchall()
        return [{"id": r[0], "to": r[1].split(","), "subject": r[2], "html": r[3], "text": r[4],
                "from": r[5], "cc": r[6].split(",") if r[6] else [], "bcc": r[7].split(",") if r[7] else [],
                "reply_to": r[8], "template_name": r[9], "template_data": json.loads(r[10]) if r[10] else {},
                "priority": r[11]} for r in rows]
    
    def mark_sent(self, id: int):
        self.conn.execute("UPDATE email_queue SET status = 'sent', sent_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), id))
        self.conn.commit()
    
    def mark_failed(self, id: int, error: str):
        self.conn.execute("UPDATE email_queue SET status = 'failed', last_error = ?, attempts = attempts + 1 WHERE id = ?", (error[:500], id))
        self.conn.commit()
    
    def retry_failed(self, max_attempts: int = 3):
        self.conn.execute("UPDATE email_queue SET status = 'pending' WHERE status = 'failed' AND attempts < ?", (max_attempts,))
        self.conn.commit()

_queue_manager = None
def get_queue_manager():
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = EmailQueueManager()
    return _queue_manager
