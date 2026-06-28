# backup/backup_service.py – Automated backup and recovery
import os
import shutil
import sqlite3
import json
import time
import tarfile
import tempfile
import hashlib
import boto3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import threading
import schedule

class BackupService:
    def __init__(self, backup_dir: str = "data/backups", config_path: str = "config/backup_config.json"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._s3_client = None
        self._azure_client = None
        self._gcs_client = None
    
    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {
            "enabled": True,
            "retention_days": 30,
            "schedule": "0 2 * * *",  # daily at 2 AM
            "verify_backups": True,
            "cloud": {
                "provider": "none",
                "bucket": "",
                "region": "",
                "access_key": "",
                "secret_key": ""
            }
        }
    
    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _get_cloud_client(self):
        provider = self.config["cloud"]["provider"]
        if provider == "aws" and not self._s3_client:
            import boto3
            self._s3_client = boto3.client(
                's3',
                region_name=self.config["cloud"]["region"],
                aws_access_key_id=self.config["cloud"]["access_key"],
                aws_secret_access_key=self.config["cloud"]["secret_key"]
            )
        elif provider == "azure" and not self._azure_client:
            from azure.storage.blob import BlobServiceClient
            conn_str = self.config["cloud"].get("connection_string")
            self._azure_client = BlobServiceClient.from_connection_string(conn_str)
        elif provider == "gcp" and not self._gcs_client:
            from google.cloud import storage
            self._gcs_client = storage.Client.from_service_account_json(self.config["cloud"]["key_file"])
        return provider
    
    def create_backup(self, backup_type: str = "full") -> Dict:
        """Create a full backup (database + FAISS index + configs + logs)"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"crownstar_backup_{timestamp}_{backup_type}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        files_backed = []
        # 1. SQLite databases (conversations, analytics, users, api_keys, rooms)
        db_files = [
            "data/conversations/crownstar_memory.db",
            "data/analytics/crownstar_analytics.db",
            "data/security/users.db",
            "data/security/api_keys.db",
            "data/collaboration/rooms.db"
        ]
        for db_file in db_files:
            src = Path(db_file)
            if src.exists():
                dst = backup_path / src.name
                shutil.copy2(src, dst)
                files_backed.append(str(src))
        
        # 2. FAISS index and mapping
        faiss_files = [
            "data/memory_store/faiss.index",
            "data/memory_store/id_map.pkl"
        ]
        for faiss_file in faiss_files:
            src = Path(faiss_file)
            if src.exists():
                dst = backup_path / src.name
                shutil.copy2(src, dst)
                files_backed.append(str(src))
        
        # 3. Configuration files
        config_files = ["config/crownstar_config.json", "config/security_config.json", "config/backup_config.json"]
        for cfg in config_files:
            src = Path(cfg)
            if src.exists():
                dst = backup_path / src.name
                shutil.copy2(src, dst)
                files_backed.append(str(src))
        
        # 4. Conversation logs (last 7 days only to save space)
        log_dir = Path("data/logs")
        if log_dir.exists():
            logs_backup = backup_path / "logs"
            logs_backup.mkdir()
            for log_file in log_dir.glob("*.jsonl"):
                if (datetime.utcnow() - datetime.fromtimestamp(log_file.stat().st_mtime)).days < 7:
                    shutil.copy2(log_file, logs_backup / log_file.name)
                    files_backed.append(str(log_file))
        
        # 5. Create metadata
        metadata = {
            "backup_name": backup_name,
            "timestamp": timestamp,
            "backup_type": backup_type,
            "files_count": len(files_backed),
            "size_bytes": sum(f.stat().st_size for f in backup_path.glob("*") if f.is_file()),
            "crownstar_version": "7.0.1"
        }
        with open(backup_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # 6. Create compressed tarball
        tar_path = self.backup_dir / f"{backup_name}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(backup_path, arcname=backup_name)
        
        # 7. Calculate checksum
        checksum = hashlib.sha256()
        with open(tar_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                checksum.update(chunk)
        checksum_file = tar_path.with_suffix(".sha256")
        checksum_file.write_text(checksum.hexdigest())
        
        # 8. Upload to cloud if configured
        provider = self._get_cloud_client()
        if provider == "aws":
            bucket = self.config["cloud"]["bucket"]
            self._s3_client.upload_file(str(tar_path), bucket, f"backups/{backup_name}.tar.gz")
        elif provider == "azure":
            container = self.config["cloud"]["container"]
            with open(tar_path, "rb") as data:
                self._azure_client.get_container_client(container).upload_blob(f"backups/{backup_name}.tar.gz", data)
        elif provider == "gcp":
            bucket = self._gcs_client.bucket(self.config["cloud"]["bucket"])
            blob = bucket.blob(f"backups/{backup_name}.tar.gz")
            blob.upload_from_filename(str(tar_path))
        
        # 9. Cleanup temporary directory
        shutil.rmtree(backup_path)
        
        # 10. Apply retention policy
        self._cleanup_old_backups()
        
        return metadata
    
    def _cleanup_old_backups(self):
        retention_days = self.config.get("retention_days", 30)
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        for backup_file in self.backup_dir.glob("crownstar_backup_*.tar.gz"):
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if mtime < cutoff:
                backup_file.unlink()
                if backup_file.with_suffix(".sha256").exists():
                    backup_file.with_suffix(".sha256").unlink()
    
    def list_backups(self) -> List[Dict]:
        backups = []
        for backup_file in sorted(self.backup_dir.glob("crownstar_backup_*.tar.gz"), reverse=True):
            metadata_file = backup_file.with_suffix(".tar.gz.meta")  # not actually saved, but we can read from within tar
            # For simplicity, extract metadata from filename
            name = backup_file.stem
            parts = name.split('_')
            if len(parts) >= 4:
                timestamp = parts[3] + '_' + parts[4] if len(parts) > 4 else parts[3]
                size_mb = backup_file.stat().st_size / (1024*1024)
                backups.append({
                    "name": name,
                    "timestamp": timestamp,
                    "size_mb": round(size_mb, 2),
                    "path": str(backup_file)
                })
        return backups
    
    def restore_backup(self, backup_name: str, restore_to: str = "latest") -> bool:
        """Restore from a backup tarball"""
        if restore_to == "latest":
            backups = self.list_backups()
            if not backups:
                return False
            backup_name = backups[0]["name"]
        
        backup_file = self.backup_dir / f"{backup_name}.tar.gz"
        if not backup_file.exists():
            return False
        
        # Verify checksum
        checksum_file = backup_file.with_suffix(".sha256")
        if checksum_file.exists():
            expected = checksum_file.read_text().strip()
            actual = hashlib.sha256()
            with open(backup_file, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    actual.update(chunk)
            if actual.hexdigest() != expected:
                raise ValueError("Checksum mismatch – backup corrupted")
        
        # Stop services? In production, would need to pause.
        # Extract to temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(tmpdir)
            extracted_dir = Path(tmpdir) / backup_name
            
            # Restore files
            # Database files – need to close existing connections before overwriting
            for db_file in extracted_dir.glob("*.db"):
                dest = Path("data") / db_file.name
                if dest.exists():
                    # In real implementation, close connections
                    pass
                shutil.copy2(db_file, dest)
            
            # FAISS index
            faiss_index = extracted_dir / "faiss.index"
            if faiss_index.exists():
                shutil.copy2(faiss_index, "data/memory_store/faiss.index")
            id_map = extracted_dir / "id_map.pkl"
            if id_map.exists():
                shutil.copy2(id_map, "data/memory_store/id_map.pkl")
            
            # Config files
            for cfg in extracted_dir.glob("*.json"):
                if cfg.name != "metadata.json":
                    shutil.copy2(cfg, "config/")
            
            # Logs
            logs_src = extracted_dir / "logs"
            if logs_src.exists():
                for log_file in logs_src.glob("*"):
                    shutil.copy2(log_file, "data/logs/")
        
        return True
    
    def verify_backups(self) -> Dict:
        """Verify integrity of all backups"""
        results = {"valid": [], "corrupt": []}
        for backup in self.list_backups():
            backup_file = Path(backup["path"])
            checksum_file = backup_file.with_suffix(".sha256")
            if not checksum_file.exists():
                results["corrupt"].append(backup["name"])
                continue
            expected = checksum_file.read_text().strip()
            actual = hashlib.sha256()
            with open(backup_file, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    actual.update(chunk)
            if actual.hexdigest() == expected:
                results["valid"].append(backup["name"])
            else:
                results["corrupt"].append(backup["name"])
        return results
    
    def start_scheduler(self):
        """Start background scheduler for automated backups"""
        schedule.clear()
        schedule.every().day.at("02:00").do(self.create_backup, "full")
        # Also schedule weekly verification
        schedule.every().sunday.at("03:00").do(self.verify_backups)
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
        thread = threading.Thread(target=run_scheduler, daemon=True)
        thread.start()
        print("Backup scheduler started (daily at 2 AM)")

# Global instance
_backup_service = None
def get_backup_service():
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service
