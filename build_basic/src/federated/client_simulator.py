# federated/client_simulator.py – Simulates a federated client
import requests, torch, numpy as np, time, json
from src.core.crownstar_core import UnifiedSuperModel, UnifiedModelConfig

class FederatedClientSimulator:
    def __init__(self, client_id, server_url="http://localhost:8080"):
        self.client_id = client_id
        self.server_url = server_url
        self.model = None
        self.local_data = None  # would load dataset

    def register(self, data_size=1000):
        resp = requests.post(f"{self.server_url}/v1/federated/register", json={
            "client_id": self.client_id,
            "endpoint": f"http://localhost:9999/client/{self.client_id}",
            "data_size": data_size
        })
        return resp.json()

    def get_global_model(self):
        resp = requests.get(f"{self.server_url}/v1/federated/model")
        if resp.status_code == 200:
            weights = resp.json()["weights"]
            # Convert to state dict
            state = {k: torch.tensor(v) for k, v in weights.items()}
            return state
        return None

    def train_locally(self, global_weights, round_id, num_epochs=1):
        # Load model with global weights
        cfg = UnifiedModelConfig()
        model = UnifiedSuperModel(cfg)
        model.load_state_dict(global_weights, strict=False)
        model.train()
        # Simulate training (dummy)
        for epoch in range(num_epochs):
            # Dummy loss
            dummy_loss = np.random.random()
        # Generate update (difference)
        new_weights = model.state_dict()
        update = {k: new_weights[k] - global_weights[k] for k in global_weights.keys()}
        return update

    def submit_update(self, round_id, update, num_samples):
        # Convert tensors to lists for JSON
        weights_serialized = {k: v.cpu().numpy().tolist() for k, v in update.items()}
        resp = requests.post(f"{self.server_url}/v1/federated/submit", json={
            "client_id": self.client_id,
            "round_id": round_id,
            "weights": weights_serialized,
            "num_samples": num_samples
        })
        return resp.json()

# Example usage (commented)
# sim = FederatedClientSimulator("client1")
# sim.register()
# global_weights = sim.get_global_model()
# update = sim.train_locally(global_weights, 0)
# sim.submit_update(0, update, 500)
