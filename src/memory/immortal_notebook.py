# src/memory/immortal_notebook.py
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from contextlib import contextmanager

class ImmortalNotebook:
    def __init__(self, db_path: str = "data/memory/notebook.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    chat_id TEXT,
                    role TEXT,
                    content TEXT,
                    metadata TEXT,
                    created_at TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            conn.commit()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_chat(self, project_id: str, title: str = "") -> str:
        chat_id = str(uuid.uuid4())[:8]
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_sessions (id, project_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (chat_id, project_id, title, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
            )
            conn.commit()
        return chat_id

    def add_message(self, chat_id: str, role: str, content: str, metadata: Dict = None) -> str:
        msg_id = str(uuid.uuid4())[:12]
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, chat_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, chat_id, role, content, json.dumps(metadata or {}), datetime.utcnow().isoformat())
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), chat_id)
            )
            conn.commit()
        return msg_id

    def get_chat_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        with self._get_connection() as conn:
            query = "SELECT id, role, content, metadata, created_at FROM messages WHERE chat_id = ? ORDER BY created_at ASC"
            if limit:
                query = f"SELECT id, role, content, metadata, created_at FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT {limit}"
            cur = conn.execute(query, (chat_id,))
            results = cur.fetchall()
            if limit:
                results = list(reversed(results))
            return [dict(row) for row in results]

    def get_project_memory(self, project_id: str, limit: int = 1000) -> List[Dict]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT m.id, m.chat_id, m.role, m.content, m.metadata, m.created_at, c.title as chat_title "
                "FROM messages m JOIN chat_sessions c ON m.chat_id = c.id "
                "WHERE c.project_id = ? ORDER BY m.created_at DESC LIMIT ?",
                (project_id, limit)
            )
            return [dict(row) for row in cur.fetchall()]

    def search_memory(self, project_id: str, query: str) -> List[Dict]:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT m.id, m.chat_id, m.role, m.content, m.metadata, m.created_at "
                "FROM messages m JOIN chat_sessions c ON m.chat_id = c.id "
                "WHERE c.project_id = ? AND m.content LIKE ? ORDER BY m.created_at DESC LIMIT 50",
                (project_id, f"%{query}%")
            )
            return [dict(row) for row in cur.fetchall()]

    def get_all_projects(self) -> List[Dict]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT project_id, COUNT(*) as chat_count, MAX(updated_at) as last_updated FROM chat_sessions GROUP BY project_id")
            return [dict(row) for row in cur.fetchall()]
