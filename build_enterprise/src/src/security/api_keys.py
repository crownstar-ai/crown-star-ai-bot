# security/api_keys.py – API key generation, validation, scopes
import secrets
import hashlib
import time
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

class APIKeyManager:
    def __init__(self, db_path: str = "data/security/api_keys.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                name TEXT,
                scopes TEXT,  -- JSON array
                rate_limit INTEGER,
                created_at TEXT,
                expires_at TEXT,
                last_used TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        self.conn.commit()
    
    def generate_key(self, user_id: str, name: str, scopes: List[str], rate_limit: int = 100, expires_days: int = 365) -> tuple:
        """Generate new API key – returns (key_id, plain_key)"""
        key_id = secrets.token_urlsafe(16)
        plain_key = f"ck_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        created = datetime.utcnow().isoformat()
        expires = (datetime.utcnow() + timedelta(days=expires_days)).isoformat()
        self.conn.execute('''
            INSERT INTO api_keys (key_id, key_hash, user_id, name, scopes, rate_limit, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (key_id, key_hash, user_id, name, json.dumps(scopes), rate_limit, created, expires))
        self.conn.commit()
        return key_id, plain_key
    
    def validate_key(self, plain_key: str) -> Optional[Dict]:
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        cursor = self.conn.execute('''
            SELECT key_id, user_id, name, scopes, rate_limit, created_at, expires_at, last_used, is_active
            FROM api_keys WHERE key_hash = ?
        ''', (key_hash,))
        row = cursor.fetchone()
        if not row:
            return None
        key_id, user_id, name, scopes_json, rate_limit, created_at, expires_at, last_used, is_active = row
        if not is_active:
            return None
        if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
            return None
        # Update last_used
        self.conn.execute('UPDATE api_keys SET last_used = ? WHERE key_id = ?', (datetime.utcnow().isoformat(), key_id))
        self.conn.commit()
        return {
            "key_id": key_id,
            "user_id": user_id,
            "name": name,
            "scopes": json.loads(scopes_json),
            "rate_limit": rate_limit,
            "created_at": created_at,
            "expires_at": expires_at
        }
    
    def revoke_key(self, key_id: str):
        self.conn.execute('UPDATE api_keys SET is_active = 0 WHERE key_id = ?', (key_id,))
        self.conn.commit()
    
    def list_keys_for_user(self, user_id: str) -> List[Dict]:
        cursor = self.conn.execute('SELECT key_id, name, created_at, expires_at, last_used, is_active FROM api_keys WHERE user_id = ?', (user_id,))
        return [{"key_id": r[0], "name": r[1], "created_at": r[2], "expires_at": r[3], "last_used": r[4], "is_active": r[5]} for r in cursor.fetchall()]
    
    def close(self):
        self.conn.close()
