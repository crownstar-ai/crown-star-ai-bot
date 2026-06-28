# audit/audit_service.py – Central audit trail service
import json
import sqlite3
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import threading
import uuid
import os

class AuditEvent:
    def __init__(self, event_type: str, user_id: str, tenant_id: str, resource: str, action: str,
                 details: Dict = None, source_ip: str = None, user_agent: str = None):
        self.event_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow().isoformat()
        self.event_type = event_type
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.resource = resource
        self.action = action
        self.details = details or {}
        self.source_ip = source_ip
        self.user_agent = user_agent
    
    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "resource": self.resource,
            "action": self.action,
            "details": self.details,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent
        }

class AuditService:
    def __init__(self, config_path: str = "config/audit/config.json", signing_key: bytes = None):
        self.config = self._load_config(config_path)
        self.db_path = "data/audit/audit.db"
        self._init_db()
        self.signing_key = signing_key or b"crownstar-audit-key-2026-32bytes!!"
        self._event_queue = []
        self._queue_lock = threading.Lock()
        self._start_flusher()
    
    def _load_config(self, path):
        default = {
            "retention_days": 365,
            "async_logging": True,
            "sign_events": True,
            "compliance_standards": ["gdpr", "soc2", "hipaa"],
            "excluded_event_types": ["health_check", "metrics_poll"]
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT,
                event_type TEXT,
                user_id TEXT,
                tenant_id TEXT,
                resource TEXT,
                action TEXT,
                details TEXT,
                source_ip TEXT,
                user_agent TEXT,
                signature TEXT
            )
        ''')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)')
        self.conn.commit()
    
    def _sign(self, data: str) -> str:
        return hmac.new(self.signing_key, data.encode(), hashlib.sha256).hexdigest()
    
    def _verify(self, data: str, signature: str) -> bool:
        expected = self._sign(data)
        return hmac.compare_digest(expected, signature)
    
    def log(self, event: AuditEvent) -> None:
        if event.event_type in self.config["excluded_event_types"]:
            return
        if self.config["async_logging"]:
            with self._queue_lock:
                self._event_queue.append(event)
        else:
            self._persist(event)
    
    def _persist(self, event: AuditEvent):
        event_dict = event.to_dict()
        event_json = json.dumps(event_dict, default=str)
        signature = self._sign(event_json) if self.config["sign_events"] else ""
        self.conn.execute('''
            INSERT INTO audit_events 
            (event_id, timestamp, event_type, user_id, tenant_id, resource, action, details, source_ip, user_agent, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.event_id, event.timestamp, event.event_type, event.user_id, event.tenant_id,
            event.resource, event.action, json.dumps(event.details), event.source_ip, event.user_agent,
            signature
        ))
        self.conn.commit()
    
    def _start_flusher(self):
        def flush_loop():
            while True:
                time.sleep(5)
                with self._queue_lock:
                    events = self._event_queue[:]
                    self._event_queue.clear()
                for ev in events:
                    self._persist(ev)
        threading.Thread(target=flush_loop, daemon=True).start()
    
    def search_events(self, start_time: datetime = None, end_time: datetime = None,
                      user_id: str = None, tenant_id: str = None, event_type: str = None,
                      resource: str = None, action: str = None, limit: int = 100) -> List[Dict]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if resource:
            query += " AND resource = ?"
            params.append(resource)
        if action:
            query += " AND action = ?"
            params.append(action)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cur = self.conn.execute(query, params)
        rows = cur.fetchall()
        results = []
        for row in rows:
            event_dict = {
                "event_id": row[0],
                "timestamp": row[1],
                "event_type": row[2],
                "user_id": row[3],
                "tenant_id": row[4],
                "resource": row[5],
                "action": row[6],
                "details": json.loads(row[7]),
                "source_ip": row[8],
                "user_agent": row[9],
                "signature": row[10]
            }
            results.append(event_dict)
        return results
    
    def verify_integrity(self, event_id: str = None) -> Dict:
        if event_id:
            cur = self.conn.execute("SELECT details, signature FROM audit_events WHERE event_id = ?", (event_id,))
            row = cur.fetchone()
            if not row:
                return {"valid": False, "reason": "Event not found"}
            valid = self._verify(row[0], row[1])
            return {"event_id": event_id, "valid": valid}
        else:
            cur = self.conn.execute("SELECT event_id, details, signature FROM audit_events")
            results = {"total": 0, "valid": 0, "invalid": []}
            for row in cur.fetchall():
                results["total"] += 1
                if self._verify(row[1], row[2]):
                    results["valid"] += 1
                else:
                    results["invalid"].append(row[0])
            return results
    
    def apply_retention(self):
        cutoff = (datetime.utcnow() - timedelta(days=self.config["retention_days"])).isoformat()
        self.conn.execute("DELETE FROM audit_events WHERE timestamp < ?", (cutoff,))
        self.conn.commit()
        return {"deleted_count": self.conn.total_changes}
    
    def export_to_csv(self, start_time: datetime, end_time: datetime, output_path: str) -> int:
        import csv
        events = self.search_events(start_time, end_time, limit=100000)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["event_id","timestamp","event_type","user_id","tenant_id","resource","action","details","source_ip","user_agent"])
            writer.writeheader()
            for ev in events:
                ev["details"] = json.dumps(ev["details"])
                writer.writerow(ev)
        return len(events)

_audit_service = None
def get_audit_service():
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
