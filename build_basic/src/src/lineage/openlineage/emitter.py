# lineage/openlineage/emitter.py – OpenLineage event emitter (stub)
import json
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
import requests
import threading
from queue import Queue

class OpenLineageEmitter:
    def __init__(self, endpoint: str = None, api_key: str = None, batch_size: int = 10):
        self.endpoint = endpoint or os.environ.get("MARQUEZ_URL", "http://localhost:5000")
        self.api_key = api_key or os.environ.get("MARQUEZ_API_KEY", "")
        self.batch_size = batch_size
        self.queue = Queue()
        self._running = True
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()
    
    def emit(self, event_type: str, event_data: Dict):
        event = {
            "eventType": event_type,
            "eventTime": datetime.utcnow().isoformat(),
            "run": {
                "runId": str(uuid.uuid4()),
                "facets": {}
            },
            "job": {
                "namespace": "crownstar",
                "name": event_data.get("job_name", "unknown"),
                "facets": {}
            },
            "inputs": event_data.get("inputs", []),
            "outputs": event_data.get("outputs", []),
            "producer": "https://github.com/crownstar/lineage"
        }
        self.queue.put(event)
    
    def _process_queue(self):
        batch = []
        while self._running:
            try:
                event = self.queue.get(timeout=5)
                batch.append(event)
                if len(batch) >= self.batch_size:
                    self._send_batch(batch)
                    batch = []
            except:
                if batch:
                    self._send_batch(batch)
                    batch = []
    
    def _send_batch(self, batch):
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            for event in batch:
                resp = requests.post(f"{self.endpoint}/api/v1/lineage", json=event, headers=headers, timeout=5)
        except Exception as e:
            print(f"Failed to send lineage event: {e}")
    
    def stop(self):
        self._running = False

_emitter = None
def get_emitter():
    global _emitter
    if _emitter is None:
        _emitter = OpenLineageEmitter()
    return _emitter
