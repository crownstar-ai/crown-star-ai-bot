# datamasking/tokenisation/token_service.py – Tokenisation vault
import sqlite3
import secrets
import hashlib
import json
from cryptography.fernet import Fernet
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class TokenisationService:
    def __init__(self, db_path: str = "data/masking/tokens/token_vault.db", encryption_key: bytes = None):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        self.encryption_key = encryption_key or Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                token_id TEXT PRIMARY KEY,
                token_value TEXT UNIQUE NOT NULL,
                original_value TEXT NOT NULL,
                data_type TEXT,
                expires_at TEXT,
                created_at TEXT,
                last_used TEXT,
                usage_count INTEGER DEFAULT 0,
                metadata TEXT
            )
        ''')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_token_value ON tokens(token_value)')
        self.conn.commit()
    
    def _encrypt_original(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()
    
    def _decrypt_original(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()
    
    def tokenize(self, value: str, data_type: str = "pii", ttl_seconds: int = None) -> str:
        """Generate a non‑reversible token (random) and store original encrypted"""
        token = secrets.token_urlsafe(16)
        encrypted_original = self._encrypt_original(value)
        expires = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat() if ttl_seconds else None
        self.conn.execute('''
            INSERT INTO tokens (token_id, token_value, original_value, data_type, expires_at, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (secrets.token_urlsafe(8), token, encrypted_original, data_type, expires, datetime.utcnow().isoformat(), json.dumps({})))
        self.conn.commit()
        return token
    
    def detokenize(self, token: str) -> Optional[str]:
        """Retrieve original value from token"""
        cur = self.conn.execute("SELECT original_value, expires_at FROM tokens WHERE token_value = ?", (token,))
        row = cur.fetchone()
        if not row:
            return None
        encrypted_original, expires_at = row
        if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
            return None
        self.conn.execute("UPDATE tokens SET last_used = ?, usage_count = usage_count + 1 WHERE token_value = ?",
                         (datetime.utcnow().isoformat(), token))
        self.conn.commit()
        return self._decrypt_original(encrypted_original)
    
    def delete_token(self, token: str) -> bool:
        cur = self.conn.execute("DELETE FROM tokens WHERE token_value = ?", (token,))
        self.conn.commit()
        return cur.rowcount > 0
    
    def list_tokens(self, limit: int = 100) -> list:
        cur = self.conn.execute("SELECT token_value, data_type, created_at, expires_at, usage_count FROM tokens LIMIT ?", (limit,))
        return [{"token": r[0], "data_type": r[1], "created": r[2], "expires": r[3], "uses": r[4]} for r in cur.fetchall()]

_token_service = None
def get_token_service():
    global _token_service
    if _token_service is None:
        _token_service = TokenisationService()
    return _token_service
