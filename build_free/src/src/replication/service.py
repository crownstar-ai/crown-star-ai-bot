# replication/service.py – Cross‑region replication and failover coordinator
import os
import time
import json
import threading
import socket
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from pathlib import Path
import sqlite3
import shutil
import requests

class ReplicationService:
    def __init__(self, config_path: str = "config/replication/config.json"):
        self.config = self._load_config(config_path)
        self.region = self.config.get("region", "primary")
        self.role = "standby"  # primary, standby
        self.leader_url = None
        self.is_running = False
        self._health_thread = None
        self._sync_thread = None
        self._replicate_queue = []
    
    def _load_config(self, path):
        default = {
            "region": "us-east-1",
            "primary_region": "us-east-1",
            "standby_regions": ["us-west-2", "eu-west-1"],
            "health_check_interval_seconds": 10,
            "sync_interval_seconds": 60,
            "failover_threshold": 3,
            "replication_backend": "cloud_storage",  # cloud_storage, direct
            "storage_provider": "aws",
            "storage_bucket": "crownstar-replication",
            "api_ports": {"primary": 8080, "standby": 8080}
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def start(self):
        self.is_running = True
        self._determine_role()
        self._health_thread = threading.Thread(target=self._health_loop, daemon=True)
        self._health_thread.start()
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        print(f"Replication service started in region {self.region} as {self.role}")
    
    def _determine_role(self):
        if self.region == self.config["primary_region"]:
            self.role = "primary"
            self.leader_url = f"http://localhost:{self.config['api_ports']['primary']}"
        else:
            self.role = "standby"
            # Attempt to find primary via health check
            primary_url = f"http://{self.config['primary_region']}:{self.config['api_ports']['primary']}"
            if self._check_health(primary_url):
                self.leader_url = primary_url
            else:
                # Primary may be down – trigger failover after threshold
                pass
    
    def _check_health(self, url) -> bool:
        try:
            resp = requests.get(f"{url}/v1/health", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def _health_loop(self):
        failures = 0
        while self.is_running:
            if self.role == "primary":
                # Primary checks its own health (no action)
                time.sleep(self.config["health_check_interval_seconds"])
                continue
            else:
                # Standby checks primary health
                primary_url = f"http://{self.config['primary_region']}:{self.config['api_ports']['primary']}"
                if not self._check_health(primary_url):
                    failures += 1
                    if failures >= self.config["failover_threshold"]:
                        self._trigger_failover()
                        failures = 0
                else:
                    failures = 0
                time.sleep(self.config["health_check_interval_seconds"])
    
    def _trigger_failover(self):
        print(f"⚠️ Primary region unhealthy, initiating failover to {self.region}")
        self.role = "primary"
        # Update local config to become primary
        self.config["primary_region"] = self.region
        self._update_config()
        # Optionally update DNS via external service
        self._update_dns("primary")
        # Notify other standbys
        for standby in self.config["standby_regions"]:
            if standby != self.region:
                try:
                    requests.post(f"http://{standby}:{self.config['api_ports']['standby']}/v1/replication/failover/notify", json={"new_primary": self.region}, timeout=2)
                except:
                    pass
    
    def _update_dns(self, role):
        # Stub – would call Route53, Cloudflare API, Azure Traffic Manager
        print(f"DNS updated: {role} region now {self.region}")
    
    def _sync_loop(self):
        from .cloud.storage import get_storage
        storage = get_storage()
        while self.is_running:
            try:
                if self.role == "primary":
                    # Primary: upload incremental changes to cloud storage
                    self._upload_incremental(storage)
                else:
                    # Standby: download latest from cloud storage and apply
                    self._download_and_apply(storage)
            except Exception as e:
                print(f"Sync error: {e}")
            time.sleep(self.config["sync_interval_seconds"])
    
    def _upload_incremental(self, storage):
        # Upload FAISS index, SQLite DB, configs to cloud
        files_to_sync = [
            ("data/memory_store/faiss.index", "faiss/index"),
            ("data/memory_store/id_map.pkl", "faiss/id_map.pkl"),
            ("data/conversations/crownstar_memory.db", "db/conversations.db"),
            ("data/analytics/crownstar_analytics.db", "db/analytics.db"),
            ("data/security/users.db", "db/users.db"),
            ("config/crownstar_config.json", "config/config.json")
        ]
        for local_path, remote_key in files_to_sync:
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    data = f.read()
                storage.upload(f"crownstar/{self.region}/{remote_key}", data)
        # Store timestamp
        storage.upload(f"crownstar/{self.region}/sync_timestamp", str(time.time()).encode())
    
    def _download_and_apply(self, storage):
        # Download latest from cloud and apply locally (standby)
        # Check if primary sync exists
        primary_prefix = f"crownstar/{self.config['primary_region']}/"
        keys = storage.list_keys(primary_prefix)
        if not keys:
            return
        # Determine latest timestamp
        timestamp_key = f"{primary_prefix}sync_timestamp"
        ts_data = storage.download(timestamp_key)
        if not ts_data:
            return
        latest_ts = float(ts_data.decode())
        # Compare with local timestamp
        local_ts_file = "data/replication/last_sync_ts.txt"
        if os.path.exists(local_ts_file):
            with open(local_ts_file, "r") as f:
                last_ts = float(f.read().strip())
            if last_ts >= latest_ts:
                return
        # Download and apply
        for key in keys:
            if key.endswith("faiss/index"):
                data = storage.download(key)
                if data:
                    with open("data/memory_store/faiss.index", "wb") as f:
                        f.write(data)
            elif key.endswith(".db"):
                data = storage.download(key)
                if data:
                    dest = key.replace(primary_prefix, "data/").replace("/", "\\")
                    with open(dest, "wb") as f:
                        f.write(data)
        with open(local_ts_file, "w") as f:
            f.write(str(latest_ts))
        print(f"Standby sync completed from {self.config['primary_region']}")
    
    def _update_config(self):
        with open("config/replication/config.json", "w") as f:
            json.dump(self.config, f, indent=2)
    
    def get_status(self) -> Dict:
        return {
            "region": self.region,
            "role": self.role,
            "leader_url": self.leader_url,
            "primary_region": self.config["primary_region"],
            "standby_regions": self.config["standby_regions"],
            "running": self.is_running
        }
    
    def trigger_manual_failover(self):
        if self.role == "standby":
            self._trigger_failover()
            return True
        return False

_rep_service = None
def get_replication_service():
    global _rep_service
    if _rep_service is None:
        _rep_service = ReplicationService()
    return _rep_service
