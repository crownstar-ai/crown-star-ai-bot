# src/analytics/usage_tracker.py
"""
Tracks usage for billing, quotas, and analytics.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.core.logging_config import get_logger
from src.database.connection import get_db_connection

logger = get_logger(__name__)


class UsageTracker:
    """Track and retrieve usage metrics."""
    
    def record_usage(
        self,
        user_id: str,
        chat_id: str,
        model: str,
        tokens: int,
        tier: str,
        cost: float = 0.0,
    ) -> str:
        """Record a usage event."""
        event_id = str(uuid.uuid4())[:12]
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usage_events
                (id, user_id, chat_id, model, tokens_used, cost, tier, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, user_id, chat_id, model, tokens, cost, tier, datetime.utcnow().isoformat()))
            conn.commit()
        logger.debug(f"Recorded usage event {event_id} for user {user_id}")
        return event_id
    
    def get_daily_count(self, user_id: str) -> int:
        """Get the number of requests made by a user today."""
        today = datetime.utcnow().date().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM usage_events
                WHERE user_id = ? AND DATE(created_at) = ?
            """, (user_id, today))
            row = cursor.fetchone()
            return row[0] if row else 0
    
    def get_usage_summary(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        tier: Optional[str] = None,
    ) -> Dict:
        """Get aggregated usage for a user in a date range."""
        query = """
            SELECT
                COUNT(*) as total_requests,
                SUM(tokens_used) as total_tokens,
                SUM(cost) as total_cost,
                AVG(cost) as avg_cost,
                tier
            FROM usage_events
            WHERE user_id = ? AND DATE(created_at) BETWEEN ? AND ?
        """
        params = [user_id, start_date, end_date]
        if tier:
            query += " AND tier = ?"
            params.append(tier)
        query += " GROUP BY tier"
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = {}
            for row in rows:
                result[row[4]] = {
                    "total_requests": row[0],
                    "total_tokens": row[1],
                    "total_cost": row[2],
                    "avg_cost": row[3],
                }
            return result
    
    def get_tenant_usage(self, tenant_id: str, start_date: str, end_date: str) -> List[Dict]:
        """Get usage for all users in a tenant."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.username, e.tier, COUNT(*) as requests, SUM(e.tokens_used) as tokens
                FROM usage_events e
                JOIN users u ON e.user_id = u.user_id
                WHERE u.tenant_id = ? AND DATE(e.created_at) BETWEEN ? AND ?
                GROUP BY u.user_id, e.tier
                ORDER BY requests DESC
            """, (tenant_id, start_date, end_date))
            rows = cursor.fetchall()
            return [
                {
                    "username": r[0],
                    "tier": r[1],
                    "requests": r[2],
                    "tokens": r[3],
                }
                for r in rows
            ]
