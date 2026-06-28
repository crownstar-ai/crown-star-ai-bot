# replication/kafka_connect/connect_client.py – Kafka Connect REST API client
import requests
import json
import os
from typing import Dict, List, Optional

class KafkaConnectClient:
    def __init__(self, connect_url: str = "http://localhost:8083"):
        self.connect_url = connect_url
    
    def list_connectors(self) -> List[str]:
        resp = requests.get(f"{self.connect_url}/connectors")
        resp.raise_for_status()
        return resp.json()
    
    def get_connector(self, name: str) -> Optional[Dict]:
        resp = requests.get(f"{self.connect_url}/connectors/{name}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    
    def create_connector(self, name: str, config: Dict) -> Dict:
        payload = {"name": name, "config": config}
        resp = requests.post(f"{self.connect_url}/connectors", json=payload)
        resp.raise_for_status()
        return resp.json()
    
    def delete_connector(self, name: str) -> bool:
        resp = requests.delete(f"{self.connect_url}/connectors/{name}")
        return resp.status_code == 204
    
    def pause_connector(self, name: str) -> bool:
        resp = requests.put(f"{self.connect_url}/connectors/{name}/pause")
        return resp.status_code == 202
    
    def resume_connector(self, name: str) -> bool:
        resp = requests.put(f"{self.connect_url}/connectors/{name}/resume")
        return resp.status_code == 202
    
    def get_connector_status(self, name: str) -> Optional[Dict]:
        resp = requests.get(f"{self.connect_url}/connectors/{name}/status")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    
    def get_connector_tasks(self, name: str) -> List[Dict]:
        resp = requests.get(f"{self.connect_url}/connectors/{name}/tasks")
        resp.raise_for_status()
        return resp.json()
    
    def restart_connector(self, name: str) -> bool:
        resp = requests.post(f"{self.connect_url}/connectors/{name}/restart")
        return resp.status_code == 204

_connect_client = None
def get_connect_client():
    global _connect_client
    if _connect_client is None:
        _connect_client = KafkaConnectClient()
    return _connect_client
