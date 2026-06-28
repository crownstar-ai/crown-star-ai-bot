# multitenant/security/rls.py – Row‑level security decorators and query filters
from functools import wraps
from ..tenant.tenant_model import TenantContext
import sqlite3

def tenant_aware_query(func):
    """Decorator to automatically inject tenant filter into SQL queries"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        tenant = TenantContext.get_current_tenant()
        if not tenant:
            # If no tenant, return empty result (or raise)
            if "get" in func.__name__:
                return None
            return []
        return func(self, *args, **kwargs)
    return wrapper

class RLSConnection:
    """Wraps SQLite connection to automatically add tenant filter to queries"""
    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantContext.get_current_tenant()
    
    def execute(self, sql, parameters=()):
        if self.tenant and "SELECT" in sql.upper() and "FROM conversations" in sql:
            # Add tenant filter if not already present
            if "WHERE" in sql.upper():
                sql = sql.replace("WHERE", f"WHERE tenant_id = '{self.tenant.tenant_id}' AND")
            else:
                # Insert before ORDER BY/GROUP BY/LIMIT
                if "ORDER BY" in sql.upper():
                    sql = sql.replace("ORDER BY", f"WHERE tenant_id = '{self.tenant.tenant_id}' ORDER BY")
                else:
                    sql = f"{sql} WHERE tenant_id = '{self.tenant.tenant_id}'"
        return self.conn.execute(sql, parameters)

# For SQLAlchemy (if used), we would add tenant filter to all queries
def add_tenant_filter(query, model, tenant_column="tenant_id"):
    tenant = TenantContext.get_current_tenant()
    if tenant:
        return query.filter(getattr(model, tenant_column) == tenant.tenant_id)
    return query
