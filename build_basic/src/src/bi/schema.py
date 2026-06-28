# bi/schema.py – Data warehouse schema and materialized views
import sqlite3
import json
from pathlib import Path
from datetime import datetime

class DataWarehouse:
    def __init__(self, db_path: str = "data/bi/crownstar_bi.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()
    
    def _init_schema(self):
        # Dimension tables
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS dim_date (
                date_id TEXT PRIMARY KEY,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                quarter INTEGER,
                week INTEGER,
                day_of_week INTEGER,
                is_weekend INTEGER
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS dim_user (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                email TEXT,
                signup_date TEXT,
                tier TEXT,
                region TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS dim_model (
                model_id TEXT PRIMARY KEY,
                model_name TEXT,
                provider TEXT,
                context_length INTEGER,
                tier_min TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS dim_tier (
                tier_id TEXT PRIMARY KEY,
                tier_name TEXT,
                price_usd REAL,
                input_limit INTEGER,
                output_limit INTEGER
            )
        ''')
        
        # Fact table: usage
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_usage (
                fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_id TEXT,
                user_id TEXT,
                model_id TEXT,
                tier_id TEXT,
                request_count INTEGER,
                input_chars INTEGER,
                output_chars INTEGER,
                total_cost REAL,
                latency_avg_ms REAL,
                latency_p99_ms REAL,
                error_count INTEGER,
                module_count INTEGER,
                FOREIGN KEY(date_id) REFERENCES dim_date(date_id),
                FOREIGN KEY(user_id) REFERENCES dim_user(user_id),
                FOREIGN KEY(model_id) REFERENCES dim_model(model_id),
                FOREIGN KEY(tier_id) REFERENCES dim_tier(tier_id)
            )
        ''')
        
        # Fact table: system_metrics (hourly)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS fact_system_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_id TEXT,
                hour INTEGER,
                cpu_avg REAL,
                memory_avg REAL,
                request_rate REAL,
                error_rate REAL,
                active_instances INTEGER
            )
        ''')
        self.conn.commit()
    
    def insert_date(self, dt: datetime):
        date_id = dt.strftime("%Y%m%d")
        self.conn.execute('''
            INSERT OR IGNORE INTO dim_date (date_id, year, month, day, quarter, week, day_of_week, is_weekend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date_id, dt.year, dt.month, dt.day, (dt.month-1)//3+1, dt.isocalendar()[1], dt.weekday(), 1 if dt.weekday() >= 5 else 0))
        self.conn.commit()
    
    def refresh_aggregates(self, start_date: str, end_date: str):
        """Refresh materialized aggregates from source analytics DB"""
        # This would query the analytics DB and insert into fact_usage
        # Placeholder – actual implementation would ETL from crownstar_analytics.db
        pass
    
    def export_to_csv(self, table_name: str, output_path: str):
        import csv
        cursor = self.conn.execute(f"SELECT * FROM {table_name}")
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([desc[0] for desc in cursor.description])
            writer.writerows(cursor.fetchall())
    
    def close(self):
        self.conn.close()

_warehouse = None
def get_warehouse():
    global _warehouse
    if _warehouse is None:
        _warehouse = DataWarehouse()
    return _warehouse
