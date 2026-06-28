# lineage/marquez/client.py – Marquez API client for lineage metadata
import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
import os

class MarquezClient:
    def __init__(self, api_url: str = None):
        self.api_url = api_url or os.environ.get("MARQUEZ_URL", "http://localhost:5000")
        self.api_version = "api/v1"
    
    def create_namespace(self, name: str, owner: str = "crownstar", description: str = "") -> Dict:
        url = f"{self.api_url}/{self.api_version}/namespaces"
        payload = {"name": name, "ownerName": owner, "description": description}
        resp = requests.post(url, json=payload)
        return resp.json()
    
    def create_source(self, namespace: str, name: str, source_type: str, connection_url: str) -> Dict:
        url = f"{self.api_url}/{self.api_version}/namespaces/{namespace}/sources"
        payload = {"name": name, "type": source_type, "connectionUrl": connection_url}
        resp = requests.post(url, json=payload)
        return resp.json()
    
    def create_dataset(self, namespace: str, name: str, physical_name: str, source_name: str) -> Dict:
        url = f"{self.api_url}/{self.api_version}/namespaces/{namespace}/datasets"
        payload = {"name": name, "physicalName": physical_name, "sourceName": source_name}
        resp = requests.post(url, json=payload)
        return resp.json()
    
    def create_job(self, namespace: str, name: str, inputs: List[str], outputs: List[str]) -> Dict:
        url = f"{self.api_url}/{self.api_version}/namespaces/{namespace}/jobs"
        payload = {"name": name, "inputs": inputs, "outputs": outputs}
        resp = requests.post(url, json=payload)
        return resp.json()
    
    def create_run(self, namespace: str, job_name: str, run_id: str) -> Dict:
        url = f"{self.api_url}/{self.api_version}/namespaces/{namespace}/jobs/{job_name}/runs"
        payload = {"id": run_id}
        resp = requests.post(url, json=payload)
        return resp.json()
    
    def get_lineage_graph(self, namespace: str, dataset: str = None, job: str = None) -> Dict:
        if dataset:
            url = f"{self.api_url}/{self.api_version}/lineage/datasets/{namespace}/{dataset}"
        elif job:
            url = f"{self.api_url}/{self.api_version}/lineage/jobs/{namespace}/{job}"
        else:
            url = f"{self.api_url}/{self.api_version}/lineage/events"
        resp = requests.get(url)
        return resp.json()
    
    def search_lineage(self, query: str) -> Dict:
        url = f"{self.api_url}/{self.api_version}/search"
        resp = requests.get(url, params={"q": query})
        return resp.json()

_marquez = None
def get_marquez():
    global _marquez
    if _marquez is None:
        _marquez = MarquezClient()
    return _marquez
