# federated/client/client.py – Federated learning client
import pickle
import base64
import copy
import time
from typing import Dict, Any, Optional, Callable
import numpy as np
import requests
import json

class FederatedClient:
    def __init__(self, client_id: str, server_url: str = "http://localhost:8080"):
        self.client_id = client_id
        self.server_url = server_url
        self.local_model: Dict[str, np.ndarray] = None
        self.local_data = None  # would hold training data in real implementation
    
    def register(self) -> bool:
        """Register this client with the federated server"""
        try:
            resp = requests.post(f"{self.server_url}/v1/federated/register", json={"client_id": self.client_id})
            return resp.status_code == 200
        except:
            return False
    
    def download_global_model(self) -> Dict[str, np.ndarray]:
        """Download current global model from server"""
        try:
            resp = requests.get(f"{self.server_url}/v1/federated/global_model")
            if resp.status_code == 200:
                data = resp.json()
                encoded = data["weights"]
                self.local_model = pickle.loads(base64.b64decode(encoded))
                return self.local_model
        except Exception as e:
            print(f"Failed to download model: {e}")
        return None
    
    def train(self, epochs: int = 1, batch_size: int = 32, learning_rate: float = 0.01) -> Dict[str, np.ndarray]:
        """Perform local training on client data (stub)"""
        # In real implementation, this would train on local dataset
        # For simulation, add small noise to weights
        if self.local_model is None:
            return None
        updated_weights = copy.deepcopy(self.local_model)
        for key in updated_weights:
            noise = np.random.normal(0, 0.01, size=updated_weights[key].shape)
            updated_weights[key] += noise
        return updated_weights
    
    def submit_update(self, round_id: int, weights: Dict[str, np.ndarray], num_samples: int) -> bool:
        """Send trained weights back to server"""
        encoded = base64.b64encode(pickle.dumps(weights)).decode('utf-8')
        payload = {
            "client_id": self.client_id,
            "round_id": round_id,
            "weights": encoded,
            "num_samples": num_samples
        }
        try:
            resp = requests.post(f"{self.server_url}/v1/federated/submit", json=payload)
            return resp.status_code == 200
        except:
            return False
    
    def run_round(self, round_id: int, epochs: int = 1) -> bool:
        """Full round: download global model, train locally, submit update"""
        model = self.download_global_model()
        if model is None:
            return False
        updated = self.train(epochs=epochs)
        if updated is None:
            return False
        # Simulate number of samples (would be actual dataset size)
        num_samples = 100 + np.random.randint(0, 50)
        return self.submit_update(round_id, updated, num_samples)

# Example client usage (for simulation)
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        client = FederatedClient(sys.argv[1])
        client.register()
        print(f"Client {sys.argv[1]} registered")
