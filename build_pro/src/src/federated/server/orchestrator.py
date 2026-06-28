# federated/server/orchestrator.py – Central server for federated learning
import json
import time
import threading
import copy
import pickle
import base64
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import os

@dataclass
class ClientUpdate:
    client_id: str
    round_id: int
    weights: Dict[str, np.ndarray]  # model parameters
    num_samples: int
    timestamp: float = field(default_factory=time.time)

@dataclass
class ClientInfo:
    client_id: str
    last_seen: float
    total_updates: int
    avg_accuracy: float = 0.0
    is_active: bool = True

class FederatedOrchestrator:
    def __init__(self, storage_dir: str = "data/federated/models"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.global_weights: Dict[str, np.ndarray] = None
        self.current_round = 0
        self.pending_updates: List[ClientUpdate] = []
        self.clients: Dict[str, ClientInfo] = {}
        self.round_state = {}  # round_id -> {status, start_time, participants}
        self.lock = threading.Lock()
        self._load_global_weights()
    
    def _load_global_weights(self):
        """Load latest global model weights if exists"""
        model_path = os.path.join(self.storage_dir, "global_model.pkl")
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                self.global_weights = pickle.load(f)
            print(f"Loaded global model from {model_path}")
    
    def save_global_weights(self):
        model_path = os.path.join(self.storage_dir, f"global_model_round_{self.current_round}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(self.global_weights, f)
        # Also save as latest
        latest_path = os.path.join(self.storage_dir, "global_model.pkl")
        with open(latest_path, "wb") as f:
            pickle.dump(self.global_weights, f)
    
    def init_global_model(self, model_weights: Dict[str, np.ndarray]):
        self.global_weights = copy.deepcopy(model_weights)
        self.current_round = 0
        self.save_global_weights()
    
    def register_client(self, client_id: str) -> ClientInfo:
        with self.lock:
            if client_id not in self.clients:
                self.clients[client_id] = ClientInfo(
                    client_id=client_id,
                    last_seen=time.time(),
                    total_updates=0
                )
            self.clients[client_id].last_seen = time.time()
            return self.clients[client_id]
    
    def start_round(self, round_id: int, min_clients: int = 2, timeout_seconds: int = 300):
        self.current_round = round_id
        self.round_state[round_id] = {
            "status": "started",
            "start_time": time.time(),
            "participants": [],
            "min_clients": min_clients,
            "timeout": timeout_seconds
        }
        self.pending_updates = []
        print(f"Round {round_id} started, waiting for updates from clients...")
    
    def submit_update(self, client_id: str, round_id: int, weights_encoded: str, num_samples: int) -> bool:
        """Receive model update from client (base64 encoded pickle)"""
        try:
            weights = pickle.loads(base64.b64decode(weights_encoded))
            update = ClientUpdate(
                client_id=client_id,
                round_id=round_id,
                weights=weights,
                num_samples=num_samples
            )
            with self.lock:
                self.pending_updates.append(update)
                if client_id in self.clients:
                    self.clients[client_id].total_updates += 1
                    self.clients[client_id].last_seen = time.time()
            print(f"Received update from {client_id} (samples={num_samples})")
            return True
        except Exception as e:
            print(f"Failed to decode update from {client_id}: {e}")
            return False
    
    def aggregate_round(self, algorithm: str = "fedavg") -> Dict[str, np.ndarray]:
        """Aggregate pending updates using specified algorithm"""
        if not self.pending_updates:
            return self.global_weights
        total_samples = sum(u.num_samples for u in self.pending_updates)
        
        if algorithm == "fedavg":
            # Weighted average
            aggregated = {}
            for key in self.global_weights.keys():
                aggregated[key] = np.zeros_like(self.global_weights[key])
            for update in self.pending_updates:
                weight = update.num_samples / total_samples
                for key in aggregated.keys():
                    aggregated[key] += update.weights[key] * weight
        elif algorithm == "fedprox":
            # FedProx adds proximal term (simplified: same as FedAvg for aggregation)
            aggregated = self._fedavg_aggregate()
        elif algorithm == "fedadam":
            # Placeholder – would use adaptive optimizer
            aggregated = self._fedavg_aggregate()
        else:
            aggregated = self._fedavg_aggregate()
        
        # Update global weights
        self.global_weights = aggregated
        self.save_global_weights()
        self.round_state[self.current_round]["status"] = "completed"
        self.round_state[self.current_round]["participants"] = [u.client_id for u in self.pending_updates]
        print(f"Round {self.current_round} aggregated with {len(self.pending_updates)} clients, total samples {total_samples}")
        return self.global_weights
    
    def _fedavg_aggregate(self) -> Dict[str, np.ndarray]:
        total_samples = sum(u.num_samples for u in self.pending_updates)
        aggregated = {}
        for key in self.global_weights.keys():
            aggregated[key] = np.zeros_like(self.global_weights[key])
        for update in self.pending_updates:
            weight = update.num_samples / total_samples if total_samples > 0 else 1.0 / len(self.pending_updates)
            for key in aggregated.keys():
                aggregated[key] += update.weights[key] * weight
        return aggregated
    
    def get_global_weights(self) -> Dict[str, np.ndarray]:
        return copy.deepcopy(self.global_weights)
    
    def get_global_weights_encoded(self) -> str:
        """Return base64 encoded pickle of global weights for distribution"""
        return base64.b64encode(pickle.dumps(self.global_weights)).decode('utf-8')
    
    def get_client_status(self, client_id: str) -> Optional[ClientInfo]:
        return self.clients.get(client_id)
    
    def get_active_clients(self, max_age_seconds: int = 300) -> List[ClientInfo]:
        now = time.time()
        return [c for c in self.clients.values() if now - c.last_seen < max_age_seconds]

# Global instance
_orchestrator = None
def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = FederatedOrchestrator()
    return _orchestrator
