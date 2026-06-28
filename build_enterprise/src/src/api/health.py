# Health check endpoint with dependency status
from fastapi import APIRouter, Depends
import os
import sys
import time
import sqlite3
import redis
from pathlib import Path

router = APIRouter()

def check_database():
    """Check database connectivity"""
    try:
        from core.config import get_settings
        settings = get_settings()
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite"):
            db_path = db_url.replace("sqlite+aiosqlite:///", "")
            if not os.path.exists(db_path):
                return {"status": "error", "message": "Database file not found"}
            conn = sqlite3.connect(db_path, timeout=1)
            conn.execute("SELECT 1")
            conn.close()
            return {"status": "ok"}
        elif db_url.startswith("postgresql"):
            # Use psycopg2 if available
            try:
                import psycopg2
                # parse URL
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url)
                conn = psycopg2.connect(
                    dbname=parsed.path[1:],
                    user=parsed.username,
                    password=parsed.password,
                    host=parsed.hostname,
                    port=parsed.port or 5432,
                    connect_timeout=2
                )
                conn.cursor().execute("SELECT 1")
                conn.close()
                return {"status": "ok"}
            except ImportError:
                return {"status": "error", "message": "psycopg2 not installed"}
        return {"status": "error", "message": "Unknown database type"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_redis():
    """Check Redis connectivity"""
    try:
        from core.config import get_settings
        settings = get_settings()
        redis_url = settings.REDIS_URL
        if not redis_url:
            return {"status": "disabled", "message": "Redis not configured"}
        r = redis.from_url(redis_url, socket_timeout=2)
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_disk_space():
    """Check free disk space (warning if < 1GB)"""
    try:
        import shutil
        stat = shutil.disk_usage("/")
        free_gb = stat.free / (1024**3)
        if free_gb < 1:
            return {"status": "warning", "free_gb": round(free_gb, 2), "message": "Low disk space"}
        return {"status": "ok", "free_gb": round(free_gb, 2)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/health")
async def health():
    """Comprehensive health check"""
    db_status = check_database()
    redis_status = check_redis()
    disk_status = check_disk_space()

    overall = "healthy"
    if db_status["status"] != "ok":
        overall = "unhealthy"
    if redis_status["status"] == "error":
        overall = "unhealthy"
    if disk_status["status"] == "error":
        overall = "unhealthy"

    return {
        "status": overall,
        "version": os.environ.get("CROWNSTAR_VERSION", "7.0.1"),
        "timestamp": time.time(),
        "checks": {
            "database": db_status,
            "redis": redis_status,
            "disk": disk_status
        }
    }
