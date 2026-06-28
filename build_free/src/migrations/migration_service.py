# src/migrations/migration_service.py – Unified migration runner
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
import json
import sqlite3

class MigrationService:
    def __init__(self, engine: str = "alembic"):
        self.engine = engine
        self.alembic_dir = Path(__file__).parent / "alembic"
        self.flyway_dir = Path(__file__).parent / "flyway"
        self.liquibase_dir = Path(__file__).parent / "liquibase"
    
    def get_current_version(self) -> str:
        if self.engine == "alembic":
            return self._alembic_current()
        elif self.engine == "flyway":
            return self._flyway_info()
        elif self.engine == "liquibase":
            return self._liquibase_status()
        return "unknown"
    
    def _alembic_current(self) -> str:
        result = subprocess.run(
            ["alembic", "-c", str(self.alembic_dir / "alembic.ini"), "current"],
            capture_output=True, text=True, cwd=self.alembic_dir
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "none"
    
    def _flyway_info(self) -> str:
        # Flyway info command (requires flyway CLI)
        result = subprocess.run(
            ["flyway", "-configFiles=" + str(self.flyway_dir / "flyway.conf"), "info"],
            capture_output=True, text=True, cwd=self.flyway_dir
        )
        return result.stdout
    
    def _liquibase_status(self) -> str:
        result = subprocess.run(
            ["liquibase", "--changeLogFile=" + str(self.liquibase_dir / "changelog.yaml"), "status"],
            capture_output=True, text=True, cwd=self.liquibase_dir
        )
        return result.stdout
    
    def migrate(self) -> bool:
        if self.engine == "alembic":
            result = subprocess.run(
                ["alembic", "-c", str(self.alembic_dir / "alembic.ini"), "upgrade", "head"],
                capture_output=True, text=True, cwd=self.alembic_dir
            )
            return result.returncode == 0
        elif self.engine == "flyway":
            result = subprocess.run(
                ["flyway", "-configFiles=" + str(self.flyway_dir / "flyway.conf"), "migrate"],
                capture_output=True, text=True, cwd=self.flyway_dir
            )
            return result.returncode == 0
        elif self.engine == "liquibase":
            result = subprocess.run(
                ["liquibase", "--changeLogFile=" + str(self.liquibase_dir / "changelog.yaml"), "update"],
                capture_output=True, text=True, cwd=self.liquibase_dir
            )
            return result.returncode == 0
        return False
    
    def rollback(self, steps: int = 1) -> bool:
        if self.engine == "alembic":
            result = subprocess.run(
                ["alembic", "-c", str(self.alembic_dir / "alembic.ini"), "downgrade", f"-{steps}"],
                capture_output=True, text=True, cwd=self.alembic_dir
            )
            return result.returncode == 0
        elif self.engine == "flyway":
            # Flyway does not support rollback easily – use baseline
            result = subprocess.run(
                ["flyway", "-configFiles=" + str(self.flyway_dir / "flyway.conf"), "baseline"],
                capture_output=True, text=True, cwd=self.flyway_dir
            )
            return False
        elif self.engine == "liquibase":
            result = subprocess.run(
                ["liquibase", "--changeLogFile=" + str(self.liquibase_dir / "changelog.yaml"), "rollbackCount", str(steps)],
                capture_output=True, text=True, cwd=self.liquibase_dir
            )
            return result.returncode == 0
        return False
    
    def history(self, limit: int = 20) -> List[Dict]:
        if self.engine == "alembic":
            result = subprocess.run(
                ["alembic", "-c", str(self.alembic_dir / "alembic.ini"), "history", "-v"],
                capture_output=True, text=True, cwd=self.alembic_dir
            )
            lines = result.stdout.splitlines()
            return [{"revision": line} for line in lines[:limit]]
        return []

_migration_service = None
def get_migration_service():
    global _migration_service
    if _migration_service is None:
        _migration_service = MigrationService(engine="alembic")
    return _migration_service
