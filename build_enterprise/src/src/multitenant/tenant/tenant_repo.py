# multitenant/tenant/tenant_repo.py – Tenant repository with row‑level security
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from .tenant_model import Tenant, TenantSettings, TenantContext

class TenantRepository:
    def __init__(self, db_path: str = "data/multitenant/tenants.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                subdomain TEXT UNIQUE,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                settings TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                metadata TEXT
            )
        ''')
        # Add tenant_id to existing tables (migration stub)
        self._migrate_tenant_id()
        self.conn.commit()
    
    def _migrate_tenant_id(self):
        # Add tenant_id column to conversations if not exists
        try:
            self.conn.execute("ALTER TABLE conversations ADD COLUMN tenant_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("ALTER TABLE users ADD COLUMN tenant_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("CREATE INDEX idx_tenant_conversations ON conversations(tenant_id)")
        except:
            pass
        self.conn.commit()
    
    def save(self, tenant: Tenant) -> None:
        self.conn.execute('''
            INSERT OR REPLACE INTO tenants
            (tenant_id, name, subdomain, plan, status, settings, created_at, updated_at, created_by, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tenant.tenant_id,
            tenant.name,
            tenant.subdomain,
            tenant.plan,
            tenant.status,
            json.dumps({"max_users": tenant.settings.max_users, "allowed_models": tenant.settings.allowed_models,
                        "max_conversations_per_user": tenant.settings.max_conversations_per_user,
                        "rate_limit_per_user": tenant.settings.rate_limit_per_user,
                        "retention_days": tenant.settings.retention_days}),
            tenant.created_at.isoformat(),
            tenant.updated_at.isoformat(),
            tenant.created_by,
            json.dumps(tenant.metadata)
        ))
        self.conn.commit()
    
    def get(self, tenant_id: str) -> Optional[Tenant]:
        cur = self.conn.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_tenant(row)
    
    def get_by_subdomain(self, subdomain: str) -> Optional[Tenant]:
        cur = self.conn.execute("SELECT * FROM tenants WHERE subdomain = ?", (subdomain,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_tenant(row)
    
    def get_by_name(self, name: str) -> Optional[Tenant]:
        cur = self.conn.execute("SELECT * FROM tenants WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_tenant(row)
    
    def list_all(self, limit: int = 100) -> List[Tenant]:
        cur = self.conn.execute("SELECT * FROM tenants LIMIT ?", (limit,))
        return [self._row_to_tenant(row) for row in cur.fetchall()]
    
    def delete(self, tenant_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
        self.conn.commit()
        return cur.rowcount > 0
    
    def _row_to_tenant(self, row) -> Tenant:
        settings_dict = json.loads(row[6]) if row[6] else {}
        settings = TenantSettings(
            max_users=settings_dict.get("max_users", 100),
            allowed_models=settings_dict.get("allowed_models", ["deepseek_v2_lite"]),
            max_conversations_per_user=settings_dict.get("max_conversations_per_user", 10000),
            rate_limit_per_user=settings_dict.get("rate_limit_per_user", 1000),
            retention_days=settings_dict.get("retention_days", 90)
        )
        return Tenant(
            tenant_id=row[0],
            name=row[1],
            subdomain=row[2],
            plan=row[3],
            status=row[4],
            settings=settings,
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
            created_by=row[9],
            metadata=json.loads(row[10]) if row[10] else {}
        )
    
    # Row‑level security enforcement helpers
    @staticmethod
    def apply_tenant_filter(table_name: str) -> str:
        """Return SQL snippet to filter by current tenant"""
        tenant = TenantContext.get_current_tenant()
        if not tenant:
            return "1=1"  # no tenant -> no rows (should not happen)
        return f"{table_name}.tenant_id = '{tenant.tenant_id}'"
    
    def enforce_tenant_on_query(self, query: str, table_name: str) -> str:
        """Inject tenant condition into SELECT query"""
        tenant_filter = self.apply_tenant_filter(table_name)
        if "WHERE" in query.upper():
            # Add AND condition
            return query.replace("WHERE", f"WHERE {tenant_filter} AND")
        else:
            # Add WHERE clause before ORDER BY/LIMIT
            if "ORDER BY" in query.upper():
                return query.replace("ORDER BY", f"WHERE {tenant_filter} ORDER BY")
            elif "LIMIT" in query.upper():
                return query.replace("LIMIT", f"WHERE {tenant_filter} LIMIT")
            else:
                return f"{query} WHERE {tenant_filter}"
    
    def get_tenant_for_user(self, user_id: str) -> Optional[Tenant]:
        """Get tenant from user record (if user belongs to a tenant)"""
        cur = self.conn.execute("SELECT tenant_id FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            return self.get(row[0])
        return None

_tenant_repo = None
def get_tenant_repo():
    global _tenant_repo
    if _tenant_repo is None:
        _tenant_repo = TenantRepository()
    return _tenant_repo
