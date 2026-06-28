# chaos/platform/gremlin/client.py – Gremlin API client
import requests
import os
from typing import Dict, List, Optional, Any

class GremlinClient:
    def __init__(self, api_key: str = None, team_id: str = None):
        self.api_key = api_key or os.environ.get("GREMLIN_API_KEY")
        self.team_id = team_id or os.environ.get("GREMLIN_TEAM_ID")
        self.base_url = "https://api.gremlin.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def create_attack(self, target_type: str, target_ids: List[str], scenario: str, duration: int = 60,
                      cpu_percent: int = 100, memory_mb: int = 500, latency_ms: int = 100) -> Dict:
        """Create a Gremlin attack (CPU, memory, latency, shutdown, etc.)"""
        payload = {
            "target": {"type": target_type, "ids": target_ids},
            "command": {"type": scenario},
            "duration": duration,
            "teamId": self.team_id
        }
        if scenario == "cpu":
            payload["command"]["cpuPercent"] = cpu_percent
        elif scenario == "memory":
            payload["command"]["memoryMB"] = memory_mb
        elif scenario == "latency":
            payload["command"]["latencyMS"] = latency_ms
        resp = requests.post(f"{self.base_url}/attacks", headers=self.headers, json=payload)
        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": resp.text, "status": resp.status_code}
    
    def list_attacks(self, limit: int = 50) -> List[Dict]:
        resp = requests.get(f"{self.base_url}/attacks?limit={limit}", headers=self.headers)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []
    
    def get_attack(self, attack_id: str) -> Dict:
        resp = requests.get(f"{self.base_url}/attacks/{attack_id}", headers=self.headers)
        if resp.status_code == 200:
            return resp.json()
        return {"error": resp.text}
    
    def halt_attack(self, attack_id: str) -> bool:
        resp = requests.delete(f"{self.base_url}/attacks/{attack_id}", headers=self.headers)
        return resp.status_code == 204
    
    def list_scenarios(self) -> List[Dict]:
        resp = requests.get(f"{self.base_url}/scenarios", headers=self.headers)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []

_gremlin = None
def get_gremlin_client():
    global _gremlin
    if _gremlin is None:
        _gremlin = GremlinClient()
    return _gremlin
