# federated/server.py – CrownStar Federated Learning Engine
import os, json, time, hashlib, copy, random, numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import OrderedDict
import torch
import torch.nn as nn
import logging

logger = logging.getLogger(__name__)

@dataclass
class ClientInfo:
    client_id: str
    endpoint: str
    data_size: int
    last_seen: int
    status: str  # active, inactive, paused
    model_version: int
    accuracy: float

@dataclass
class ModelUpdate:
    client_id: str
    round_id: int
    weights: Dict[str, torch.Tensor]
    num_samples: int
    timestamp: int
    metadata: Dict

class FederatedServer:
    """Central server for federated learning – aggregates client updates."""
    def __init__(self, config_path="config/federated/server_config.json"):
        self.config = self._load_config(config_path)
        self.global_model: Optional[nn.Module] = None
        self.clients: Dict[str, ClientInfo] = {}
        self.updates: List[ModelUpdate] = []
        self.current_round = 0
        self.round_history = []
        self._load_model()

    def _load_config(self, path):
        default = {
            "aggregation_algorithm": "fedavg",  # fedavg, fedprox, scaffold
            "num_rounds": 100,
            "min_clients_per_round": 5,
            "client_fraction": 0.3,
            "secure_aggregation": True,
            "differential_privacy": {
                "enabled": True,
                "epsilon": 1.0,
                "delta": 1e-5,
                "noise_multiplier": 0.5
            },
            "model": {
                "architecture": "unified_super_model",
                "input_dim": 64,
                "hidden_dims": [128, 64],
                "output_dim": 100
            },
            "checkpoint_dir": "data/federated/models"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        os.makedirs(default["checkpoint_dir"], exist_ok=True)
        return default

    def _load_model(self):
        # Load or initialize global model
        from src.core.crownstar_core import UnifiedSuperModel
        from src.core.model_config import UnifiedModelConfig
        cfg = UnifiedModelConfig(
            input_dim=self.config["model"]["input_dim"],
            hidden_dims=self.config["model"]["hidden_dims"],
            output_dim=self.config["model"]["output_dim"],
            device="cpu"
        )
        self.global_model = UnifiedSuperModel(cfg)
        # Load latest checkpoint if exists
        checkpoint_path = os.path.join(self.config["checkpoint_dir"], "global_model.pt")
        if os.path.exists(checkpoint_path):
            self.global_model.load_state_dict(torch.load(checkpoint_path, map_location="cpu"))
            logger.info("Loaded global model checkpoint")
        self.global_model.eval()

    def register_client(self, client_id: str, endpoint: str, data_size: int, metadata: Dict = None) -> bool:
        """Register a new client for federated learning."""
        if client_id not in self.clients:
            self.clients[client_id] = ClientInfo(
                client_id=client_id,
                endpoint=endpoint,
                data_size=data_size,
                last_seen=int(time.time()),
                status="active",
                model_version=self.current_round,
                accuracy=0.0
            )
            logger.info(f"Client {client_id} registered (data size: {data_size})")
            return True
        return False

    def select_clients(self, round_id: int) -> List[ClientInfo]:
        """Select a subset of clients for this training round."""
        active = [c for c in self.clients.values() if c.status == "active"]
        if not active:
            return []
        num_clients = max(self.config["min_clients_per_round"], int(len(active) * self.config["client_fraction"]))
        # Power‑of‑choice selection: sample a larger pool, then pick top by data size
        candidates = random.sample(active, min(len(active), num_clients * 2))
        selected = sorted(candidates, key=lambda x: x.data_size, reverse=True)[:num_clients]
        logger.info(f"Round {round_id}: selected {len(selected)} clients")
        return selected

    def distribute_model(self, client: ClientInfo) -> Dict:
        """Send current global model weights to a client."""
        state_dict = {k: v.cpu().numpy().tolist() for k, v in self.global_model.state_dict().items()}
        return {
            "round_id": self.current_round,
            "model_weights": state_dict,
            "model_version": self.current_round,
            "timestamp": int(time.time())
        }

    def receive_update(self, update: ModelUpdate) -> bool:
        """Receive a model update from a client, store it for aggregation."""
        # Validate update
        if update.round_id != self.current_round:
            logger.warning(f"Update from {update.client_id} has stale round {update.round_id}")
            return False
        # Store
        self.updates.append(update)
        # Update client last seen
        if update.client_id in self.clients:
            self.clients[update.client_id].last_seen = int(time.time())
        logger.debug(f"Received update from {update.client_id} (samples: {update.num_samples})")
        return True

    def aggregate(self) -> Dict:
        """Perform federated aggregation (FedAvg with optional differential privacy)."""
        if not self.updates:
            return {"status": "no_updates"}
        total_samples = sum(u.num_samples for u in self.updates)
        # Initialize aggregated weights as zero dict
        agg_weights = OrderedDict()
        for key in self.updates[0].weights.keys():
            agg_weights[key] = torch.zeros_like(self.updates[0].weights[key])

        # Weighted average
        for update in self.updates:
            weight = update.num_samples / total_samples
            for key in agg_weights.keys():
                agg_weights[key] += weight * update.weights[key]

        # Differential privacy: add noise to each weight (if enabled)
        if self.config["differential_privacy"]["enabled"]:
            dp_cfg = self.config["differential_privacy"]
            noise_scale = dp_cfg["noise_multiplier"] * dp_cfg["epsilon"] / (total_samples + 1e-8)
            for key in agg_weights.keys():
                noise = torch.normal(0, noise_scale, size=agg_weights[key].shape)
                agg_weights[key] += noise

        # Update global model
        self.global_model.load_state_dict(agg_weights, strict=False)
        # Save checkpoint
        checkpoint_path = os.path.join(self.config["checkpoint_dir"], f"global_model_round_{self.current_round}.pt")
        torch.save(self.global_model.state_dict(), checkpoint_path)
        # Also save as latest
        latest_path = os.path.join(self.config["checkpoint_dir"], "global_model.pt")
        torch.save(self.global_model.state_dict(), latest_path)

        # Record round history
        round_metrics = {
            "round": self.current_round,
            "num_clients": len(self.updates),
            "total_samples": total_samples,
            "timestamp": int(time.time()),
            "model_size_mb": sum(p.numel() * p.element_size() for p in self.global_model.parameters()) / (1024*1024)
        }
        self.round_history.append(round_metrics)
        # Clear updates for next round
        self.updates.clear()
        self.current_round += 1
        logger.info(f"Aggregation complete for round {self.current_round-1}: {len(round_metrics)} clients")
        return round_metrics

    def get_client_status(self) -> List[Dict]:
        """Return status of all registered clients."""
        return [asdict(c) for c in self.clients.values()]

    def get_global_model(self) -> Dict:
        """Return current global model weights (for distribution)."""
        state_dict = {k: v.cpu().numpy().tolist() for k, v in self.global_model.state_dict().items()}
        return {"round": self.current_round, "weights": state_dict}

    def start_training_round(self, background=False):
        """Initiate a new federated round: select clients, distribute model, wait for updates (async)."""
        selected = self.select_clients(self.current_round)
        if not selected:
            return {"status": "no_clients_available"}
        # In production, would send model to clients asynchronously
        # For now, simulate by calling client endpoints via requests
        # (Placeholder – actual client communication would be implemented)
        return {"status": "round_initiated", "selected_clients": [c.client_id for c in selected]}

_fed_server = None
def get_fed_server():
    global _fed_server
    if _fed_server is None:
        _fed_server = FederatedServer()
    return _fed_server
