# experiments/service.py – A/B testing and feature flag management
import json
import hashlib
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import math
import random

class ExperimentService:
    def __init__(self, db_path: str = "data/experiments/experiments.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                variants TEXT,  -- JSON: {"control": 50, "variant_a": 50}
                start_time TEXT,
                end_time TEXT,
                status TEXT,  -- draft, running, paused, completed
                target_metric TEXT,
                min_sample_size INTEGER,
                created_at TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                user_id TEXT,
                variant TEXT,
                assigned_at TEXT,
                FOREIGN KEY(experiment_id) REFERENCES experiments(id)
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                user_id TEXT,
                variant TEXT,
                event_type TEXT,  -- conversion, latency, token_count
                value REAL,
                timestamp TEXT,
                FOREIGN KEY(experiment_id) REFERENCES experiments(id)
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS feature_flags (
                key TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                rollout_percentage INTEGER DEFAULT 0,
                description TEXT,
                updated_at TEXT
            )
        ''')
        self.conn.commit()
    
    def create_experiment(self, name: str, variants: Dict[str, int], target_metric: str = "conversion", min_sample_size: int = 1000) -> str:
        exp_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:8]
        now = datetime.utcnow().isoformat()
        self.conn.execute('''
            INSERT INTO experiments (id, name, variants, start_time, end_time, status, target_metric, min_sample_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exp_id, name, json.dumps(variants), now, None, "draft", target_metric, min_sample_size, now))
        self.conn.commit()
        return exp_id
    
    def start_experiment(self, exp_id: str):
        self.conn.execute('UPDATE experiments SET status = "running", start_time = ? WHERE id = ?', (datetime.utcnow().isoformat(), exp_id))
        self.conn.commit()
    
    def stop_experiment(self, exp_id: str):
        self.conn.execute('UPDATE experiments SET status = "completed", end_time = ? WHERE id = ?', (datetime.utcnow().isoformat(), exp_id))
        self.conn.commit()
    
    def assign_variant(self, exp_id: str, user_id: str) -> str:
        # Check existing assignment
        cursor = self.conn.execute('SELECT variant FROM assignments WHERE experiment_id = ? AND user_id = ?', (exp_id, user_id))
        row = cursor.fetchone()
        if row:
            return row[0]
        # Get experiment variants
        cursor = self.conn.execute('SELECT variants FROM experiments WHERE id = ?', (exp_id,))
        row = cursor.fetchone()
        if not row:
            return None
        variants = json.loads(row[0])
        # Deterministic bucketing (consistent hash)
        hash_val = int(hashlib.md5(f"{exp_id}:{user_id}".encode()).hexdigest()[:8], 16)
        total = sum(variants.values())
        bucket = hash_val % total
        cumulative = 0
        for variant, weight in variants.items():
            cumulative += weight
            if bucket < cumulative:
                self.conn.execute('INSERT INTO assignments (experiment_id, user_id, variant, assigned_at) VALUES (?, ?, ?, ?)',
                                 (exp_id, user_id, variant, datetime.utcnow().isoformat()))
                self.conn.commit()
                return variant
        return list(variants.keys())[0]
    
    def track_event(self, exp_id: str, user_id: str, event_type: str, value: float = 1.0):
        # Get user's variant
        cursor = self.conn.execute('SELECT variant FROM assignments WHERE experiment_id = ? AND user_id = ?', (exp_id, user_id))
        row = cursor.fetchone()
        if not row:
            return
        variant = row[0]
        self.conn.execute('''
            INSERT INTO events (experiment_id, user_id, variant, event_type, value, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (exp_id, user_id, variant, event_type, value, datetime.utcnow().isoformat()))
        self.conn.commit()
    
    def get_results(self, exp_id: str) -> Dict:
        cursor = self.conn.execute('SELECT name, variants, target_metric, min_sample_size FROM experiments WHERE id = ?', (exp_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        name, variants_json, target_metric, min_sample_size = row
        variants = json.loads(variants_json)
        results = {}
        for variant in variants.keys():
            # Count conversions and total assignments
            cursor_conv = self.conn.execute('SELECT COUNT(*) FROM events WHERE experiment_id = ? AND variant = ? AND event_type = ?', (exp_id, variant, target_metric))
            conversions = cursor_conv.fetchone()[0]
            cursor_assign = self.conn.execute('SELECT COUNT(*) FROM assignments WHERE experiment_id = ? AND variant = ?', (exp_id, variant))
            total = cursor_assign.fetchone()[0]
            conversion_rate = conversions / total if total > 0 else 0
            results[variant] = {"conversions": conversions, "total": total, "rate": conversion_rate}
        # Statistical significance (Z-test between control and best variant)
        control = results.get("control", {})
        control_rate = control.get("rate", 0)
        control_n = control.get("total", 0)
        best_variant = max(results.items(), key=lambda x: x[1]["rate"])[0] if results else None
        if best_variant and best_variant != "control" and control_n > 0:
            best = results[best_variant]
            p_value = self._z_test(control_rate, control_n, best["rate"], best["total"])
            results["significance"] = {"p_value": p_value, "significant": p_value < 0.05, "winner": best_variant if p_value < 0.05 else None}
        return {"experiment_id": exp_id, "name": name, "target_metric": target_metric, "results": results}
    
    def _z_test(self, rate1: float, n1: int, rate2: float, n2: int) -> float:
        import math
        p_pool = (rate1 * n1 + rate2 * n2) / (n1 + n2)
        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        if se == 0:
            return 1.0
        z = (rate2 - rate1) / se
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        return p
    
    # Feature flags
    def set_feature_flag(self, key: str, enabled: bool, rollout_percentage: int = 100, description: str = ""):
        self.conn.execute('''
            INSERT OR REPLACE INTO feature_flags (key, enabled, rollout_percentage, description, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (key, 1 if enabled else 0, rollout_percentage, description, datetime.utcnow().isoformat()))
        self.conn.commit()
    
    def is_feature_enabled(self, key: str, user_id: str = None) -> bool:
        cursor = self.conn.execute('SELECT enabled, rollout_percentage FROM feature_flags WHERE key = ?', (key,))
        row = cursor.fetchone()
        if not row:
            return False
        enabled, rollout = row
        if not enabled:
            return False
        if rollout >= 100:
            return True
        if user_id:
            hash_val = int(hashlib.md5(f"{key}:{user_id}".encode()).hexdigest()[:8], 16)
            return (hash_val % 100) < rollout
        return random.random() * 100 < rollout
    
    def list_feature_flags(self) -> List[Dict]:
        cursor = self.conn.execute('SELECT key, enabled, rollout_percentage, description, updated_at FROM feature_flags')
        return [{"key": r[0], "enabled": bool(r[1]), "rollout": r[2], "description": r[3], "updated_at": r[4]} for r in cursor.fetchall()]

_exp_service = None
def get_exp_service():
    global _exp_service
    if _exp_service is None:
        _exp_service = ExperimentService()
    return _exp_service
