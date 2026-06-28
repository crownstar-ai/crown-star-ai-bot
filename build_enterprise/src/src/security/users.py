# security/users.py – User accounts, authentication, password hashing
import sqlite3
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from .encryption import get_encryption

class UserManager:
    def __init__(self, db_path: str = "data/security/users.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        self.enc = get_encryption()
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                last_login TEXT,
                metadata TEXT
            )
        ''')
        # Create default admin if none exists
        cursor = self.conn.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            self._create_default_admin()
        self.conn.commit()
    
    def _create_default_admin(self):
        from .rbac import PERM_ADMIN
        password = secrets.token_urlsafe(12)
        hash_pw, salt = self.enc.hash_password(password)
        user_id = "user_" + secrets.token_urlsafe(8)
        self.conn.execute('''
            INSERT INTO users (user_id, username, email, password_hash, password_salt, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        ''', (user_id, "admin", "admin@crownstar.local", hash_pw, salt, "admin", datetime.utcnow().isoformat()))
        self.conn.commit()
        print(f"Default admin created. Password: {password}")
    
    def create_user(self, username: str, email: str, password: str, role: str = "user") -> str:
        user_id = "user_" + secrets.token_urlsafe(8)
        hash_pw, salt = self.enc.hash_password(password)
        self.conn.execute('''
            INSERT INTO users (user_id, username, email, password_hash, password_salt, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        ''', (user_id, username, email, hash_pw, salt, role, datetime.utcnow().isoformat()))
        self.conn.commit()
        return user_id
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        cursor = self.conn.execute('SELECT user_id, username, email, password_hash, password_salt, role, is_active, created_at FROM users WHERE username = ? OR email = ?', (username, username))
        row = cursor.fetchone()
        if not row:
            return None
        user_id, uname, email, hash_pw, salt, role, is_active, created = row
        if not is_active:
            return None
        if self.enc.verify_password(password, hash_pw, salt):
            self.conn.execute('UPDATE users SET last_login = ? WHERE user_id = ?', (datetime.utcnow().isoformat(), user_id))
            self.conn.commit()
            return {"user_id": user_id, "username": uname, "email": email, "role": role}
        return None
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        cursor = self.conn.execute('SELECT user_id, username, email, role, is_active, created_at, last_login FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return {"user_id": row[0], "username": row[1], "email": row[2], "role": row[3], "is_active": row[4], "created_at": row[5], "last_login": row[6]}
        return None
    
    def update_role(self, user_id: str, new_role: str):
        self.conn.execute('UPDATE users SET role = ? WHERE user_id = ?', (new_role, user_id))
        self.conn.commit()
    
    def list_users(self) -> List[Dict]:
        cursor = self.conn.execute('SELECT user_id, username, email, role, is_active, created_at, last_login FROM users')
        return [{"user_id": r[0], "username": r[1], "email": r[2], "role": r[3], "is_active": r[4], "created_at": r[5], "last_login": r[6]} for r in cursor.fetchall()]
    
    def close(self):
        self.conn.close()
