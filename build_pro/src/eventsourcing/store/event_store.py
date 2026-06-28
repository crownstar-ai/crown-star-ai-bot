# eventsourcing/store/event_store.py – Event store
import json, sqlite3, os
from pathlib import Path

class EventStore:
    def __init__(self, config=None):
        self.backend = "sqlite"
        self._sqlite_conn = None
        self._init_sqlite()
    
    def _init_sqlite(self):
        db_path = "data/eventsourcing/eventstore.db"
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
        self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                aggregate_id TEXT,
                aggregate_type TEXT,
                event_type TEXT,
                event_version INTEGER,
                event_data TEXT,
                timestamp TEXT
            )
        ''')
        self._sqlite_conn.execute('CREATE INDEX IF NOT EXISTS idx_aggregate ON events(aggregate_id, event_version)')
        self._sqlite_conn.commit()
    
    def append_events(self, aggregate_id: str, expected_version: int, events: list) -> bool:
        cursor = self._sqlite_conn.cursor()
        cursor.execute("SELECT MAX(event_version) FROM events WHERE aggregate_id = ?", (aggregate_id,))
        row = cursor.fetchone()
        current = row[0] if row[0] else 0
        if current != expected_version:
            return False
        for ev in events:
            cursor.execute(
                "INSERT INTO events (event_id, aggregate_id, aggregate_type, event_type, event_version, event_data, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ev.event_id, aggregate_id, ev.aggregate_type, ev.event_type, ev.version, json.dumps(ev.data, default=str), ev.timestamp.isoformat())
            )
        self._sqlite_conn.commit()
        return True
    
    def load_events(self, aggregate_id: str) -> list:
        from ..events.event_defs import event_from_dict
        cursor = self._sqlite_conn.execute(
            "SELECT event_type, aggregate_id, event_data, timestamp, event_version FROM events WHERE aggregate_id = ? ORDER BY event_version ASC",
            (aggregate_id,)
        )
        events = []
        for row in cursor.fetchall():
            ev = event_from_dict({
                "event_type": row[0],
                "aggregate_id": row[1],
                "data": json.loads(row[2]),
                "timestamp": row[3]
            })
            ev.version = row[4]
            events.append(ev)
        return events

_event_store = None
def get_event_store():
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store
