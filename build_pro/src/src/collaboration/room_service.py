# collaboration/room_service.py – Room management, presence, shared state
import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path
import asyncio
import uuid

class RoomService:
    def __init__(self, db_path: str = "data/collaboration/rooms.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        # In‑memory presence tracking (active WebSocket connections)
        self.room_presence: Dict[str, Dict[str, dict]] = {}  # room_id -> {user_id -> presence_info}
        self.room_states: Dict[str, dict] = {}  # room_id -> shared state (modules, tier, model)
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                owner_id TEXT,
                created_at TEXT,
                is_private INTEGER DEFAULT 0,
                metadata TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS room_members (
                room_id TEXT,
                user_id TEXT,
                joined_at TEXT,
                role TEXT DEFAULT 'member',
                PRIMARY KEY (room_id, user_id)
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS room_messages (
                message_id TEXT PRIMARY KEY,
                room_id TEXT,
                user_id TEXT,
                username TEXT,
                content TEXT,
                timestamp TEXT,
                is_system INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()
    
    def create_room(self, name: str, owner_id: str, is_private: bool = False) -> str:
        room_id = str(uuid.uuid4())[:8]
        self.conn.execute('INSERT INTO rooms (room_id, name, owner_id, created_at, is_private) VALUES (?, ?, ?, ?, ?)',
                         (room_id, name, owner_id, datetime.utcnow().isoformat(), 1 if is_private else 0))
        self.conn.commit()
        # Auto‑join owner
        self.join_room(room_id, owner_id, role="owner")
        # Initialise shared state
        self.room_states[room_id] = {
            "modules": {},
            "tier": "free_pay_per_use",
            "model": "deepseek_v2_lite",
            "updated_at": time.time()
        }
        return room_id
    
    def join_room(self, room_id: str, user_id: str, role: str = "member") -> bool:
        cursor = self.conn.execute('SELECT room_id FROM rooms WHERE room_id = ?', (room_id,))
        if not cursor.fetchone():
            return False
        self.conn.execute('INSERT OR IGNORE INTO room_members (room_id, user_id, joined_at, role) VALUES (?, ?, ?, ?)',
                         (room_id, user_id, datetime.utcnow().isoformat(), role))
        self.conn.commit()
        # Add to presence
        if room_id not in self.room_presence:
            self.room_presence[room_id] = {}
        self.room_presence[room_id][user_id] = {
            "joined_at": time.time(),
            "last_seen": time.time(),
            "typing": False
        }
        return True
    
    def leave_room(self, room_id: str, user_id: str):
        self.conn.execute('DELETE FROM room_members WHERE room_id = ? AND user_id = ?', (room_id, user_id))
        self.conn.commit()
        if room_id in self.room_presence and user_id in self.room_presence[room_id]:
            del self.room_presence[room_id][user_id]
    
    def get_room(self, room_id: str) -> Optional[Dict]:
        cursor = self.conn.execute('SELECT room_id, name, owner_id, created_at, is_private, metadata FROM rooms WHERE room_id = ?', (room_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {"room_id": row[0], "name": row[1], "owner_id": row[2], "created_at": row[3], "is_private": row[4], "metadata": row[5]}
    
    def list_rooms(self, user_id: str = None) -> List[Dict]:
        if user_id:
            cursor = self.conn.execute('''
                SELECT r.room_id, r.name, r.owner_id, r.created_at, r.is_private
                FROM rooms r JOIN room_members m ON r.room_id = m.room_id
                WHERE m.user_id = ?
            ''', (user_id,))
        else:
            cursor = self.conn.execute('SELECT room_id, name, owner_id, created_at, is_private FROM rooms WHERE is_private = 0')
        return [{"room_id": r[0], "name": r[1], "owner_id": r[2], "created_at": r[3], "is_private": r[4]} for r in cursor.fetchall()]
    
    def save_message(self, room_id: str, user_id: str, username: str, content: str, is_system: bool = False) -> str:
        msg_id = str(uuid.uuid4())[:8]
        self.conn.execute('''
            INSERT INTO room_messages (message_id, room_id, user_id, username, content, timestamp, is_system)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (msg_id, room_id, user_id, username, content, datetime.utcnow().isoformat(), 1 if is_system else 0))
        self.conn.commit()
        return msg_id
    
    def get_messages(self, room_id: str, limit: int = 50) -> List[Dict]:
        cursor = self.conn.execute('''
            SELECT message_id, user_id, username, content, timestamp, is_system
            FROM room_messages WHERE room_id = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (room_id, limit))
        rows = cursor.fetchall()
        return [{"message_id": r[0], "user_id": r[1], "username": r[2], "content": r[3], "timestamp": r[4], "is_system": r[5]} for r in reversed(rows)]
    
    def update_shared_state(self, room_id: str, updates: dict):
        if room_id not in self.room_states:
            self.room_states[room_id] = {}
        self.room_states[room_id].update(updates)
        self.room_states[room_id]["updated_at"] = time.time()
    
    def get_shared_state(self, room_id: str) -> dict:
        return self.room_states.get(room_id, {})
    
    def update_presence(self, room_id: str, user_id: str, typing: bool = None):
        if room_id in self.room_presence and user_id in self.room_presence[room_id]:
            if typing is not None:
                self.room_presence[room_id][user_id]["typing"] = typing
            self.room_presence[room_id][user_id]["last_seen"] = time.time()
    
    def get_presence(self, room_id: str) -> List[Dict]:
        if room_id not in self.room_presence:
            return []
        return [{"user_id": uid, "joined_at": info["joined_at"], "last_seen": info["last_seen"], "typing": info.get("typing", False)} 
                for uid, info in self.room_presence[room_id].items()]
    
    def close(self):
        self.conn.close()

# Global instance
_room_service = None
def get_room_service():
    global _room_service
    if _room_service is None:
        _room_service = RoomService()
    return _room_service
