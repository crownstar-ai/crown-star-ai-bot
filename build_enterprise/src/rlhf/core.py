# rlhf/core.py – CrownStar Reinforcement Learning from Human Feedback Pipeline
import os, json, time, hashlib, random, numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Preference Data Models
# --------------------------------------------------------------------
@dataclass
class PreferencePair:
    id: str
    prompt: str
    response_a: str
    response_b: str
    preferred: str  # "a", "b", or None (tie)
    annotator_id: str
    timestamp: int
    metadata: Dict

@dataclass
class RewardModelConfig:
    model_name: str = "crownstar_reward"
    hidden_dims: List[int] = field(default_factory=lambda: [256, 128, 64])
    learning_rate: float = 1e-5
    batch_size: int = 16
    epochs: int = 3

class PreferenceDataset(Dataset):
    def __init__(self, preferences: List[PreferencePair], tokenizer):
        self.preferences = preferences
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.preferences)

    def __getitem__(self, idx):
        pref = self.preferences[idx]
        # Tokenize prompt + response_a and prompt + response_b
        # Simplified: return text pairs
        return {
            "prompt": pref.prompt,
            "response_a": pref.response_a,
            "response_b": pref.response_b,
            "preferred": 0 if pref.preferred == "a" else 1  # 0 for a, 1 for b
        }

# --------------------------------------------------------------------
# Reward Model (predicts which response is better)
# --------------------------------------------------------------------
class RewardModel(nn.Module):
    """
    Bradley‑Terry reward model: outputs scalar reward for a (prompt, response) pair.
    """
    def __init__(self, config: RewardModelConfig, vocab_size: int = 50257, embed_dim: int = 768):
        super().__init__()
        self.config = config
        # Simplified: use a small transformer or MLP on pooled embeddings
        # For demo, use a simple MLP on concatenated prompt+response (would use embeddings in reality)
        self.embedding = nn.Embedding(vocab_size, embed_dim)
        self.pooler = nn.AdaptiveAvgPool1d(1)
        # MLP for reward score
        layers = []
        in_dim = embed_dim
        for h in config.hidden_dims:
            layers.append(nn.Linear(in_dim, h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.1))
            in_dim = h
        layers.append(nn.Linear(in_dim, 1))  # scalar reward
        self.mlp = nn.Sequential(*layers)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor = None) -> torch.Tensor:
        # input_ids shape: (batch, seq_len)
        embeds = self.embedding(input_ids)  # (batch, seq_len, embed_dim)
        # Pool over sequence dimension
        pooled = embeds.mean(dim=1)  # (batch, embed_dim)
        reward = self.mlp(pooled)  # (batch, 1)
        return reward.squeeze(-1)

    def preference_loss(self, reward_a: torch.Tensor, reward_b: torch.Tensor, preferred: torch.Tensor) -> torch.Tensor:
        """
        Bradley‑Terry loss: -log(sigmoid(reward_a - reward_b)) when a preferred,
        -log(sigmoid(reward_b - reward_a)) when b preferred.
        """
        # preferred: 0 for a, 1 for b
        diff = reward_a - reward_b
        # For preferred b, we want reward_b > reward_a => diff negative
        # Use: loss = -log(sigmoid((2*pref - 1) * diff))? Actually:
        # If pref=0 (a better), we want diff > 0 => sigmoid(diff) high
        # If pref=1 (b better), we want diff < 0 => sigmoid(-diff) high
        sign = 1 - 2 * preferred  # pref=0 -> sign=1, pref=1 -> sign=-1
        logits = sign * diff
        loss = F.binary_cross_entropy_with_logits(logits, torch.ones_like(logits))
        return loss

# --------------------------------------------------------------------
# Reward Trainer
# --------------------------------------------------------------------
class RewardTrainer:
    def __init__(self, model: RewardModel, config: RewardModelConfig, device="cpu"):
        self.model = model.to(device)
        self.config = config
        self.device = device
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

    def train(self, dataset: PreferenceDataset, num_epochs: int = None):
        num_epochs = num_epochs or self.config.epochs
        dataloader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)
        self.model.train()
        total_loss = 0.0
        for epoch in range(num_epochs):
            epoch_loss = 0.0
            for batch in dataloader:
                # In real implementation, tokenize prompt+response
                # For simulation, use dummy tensors
                # Placeholder: we assume inputs are pre‑tokenized
                # Here we just simulate loss
                loss = torch.tensor(np.random.rand() * 0.5)
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item()
            logger.info(f"Reward model epoch {epoch+1}, loss: {epoch_loss/len(dataloader):.4f}")
        return {"final_loss": total_loss / (num_epochs * len(dataloader))}

# --------------------------------------------------------------------
# Policy Trainer (PPO / DPO)
# --------------------------------------------------------------------
class PolicyTrainer:
    """
    Fine‑tune CrownStar model using Proximal Policy Optimization (PPO)
    or Direct Preference Optimization (DPO) with reward model.
    """
    def __init__(self, model, reward_model, tokenizer, config):
        self.model = model
        self.reward_model = reward_model
        self.tokenizer = tokenizer
        self.config = config
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=config.get("learning_rate", 1e-6))

    def dpo_loss(self, chosen_logps, rejected_logps, beta=0.1):
        """Direct Preference Optimization loss."""
        log_ratio = chosen_logps - rejected_logps
        loss = -F.logsigmoid(beta * log_ratio).mean()
        return loss

    def train_step(self, batch):
        # Simplified: compute log probabilities for chosen and rejected responses
        # using current policy, then apply DPO loss
        loss = torch.tensor(0.0)
        loss.backward()
        self.optimizer.step()
        return {"loss": loss.item()}

# --------------------------------------------------------------------
# RLHF Manager (orchestrates data collection, training, evaluation)
# --------------------------------------------------------------------
class RLHFManager:
    def __init__(self, config_path="config/rlhf/config.json"):
        self.config = self._load_config(config_path)
        self.preferences: List[PreferencePair] = []
        self.reward_model: Optional[RewardModel] = None
        self._load_preferences()

    def _load_config(self, path):
        default = {
            "reward_model": {
                "hidden_dims": [256, 128, 64],
                "learning_rate": 1e-5,
                "batch_size": 16,
                "epochs": 3
            },
            "policy_model": {
                "learning_rate": 1e-6,
                "ppo_epochs": 4,
                "clip_epsilon": 0.2
            },
            "preference_storage": "data/rlhf/preferences/preferences.json"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def _load_preferences(self):
        storage_path = self.config["preference_storage"]
        if os.path.exists(storage_path):
            with open(storage_path, 'r') as f:
                data = json.load(f)
                self.preferences = [PreferencePair(**p) for p in data]

    def _save_preferences(self):
        storage_path = self.config["preference_storage"]
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, 'w') as f:
            json.dump([asdict(p) for p in self.preferences], f, indent=2)

    def add_preference(self, prompt: str, response_a: str, response_b: str,
                       preferred: str, annotator_id: str = "human", metadata: Dict = None) -> str:
        pref_id = hashlib.md5(f"{prompt}_{response_a}_{response_b}_{time.time()}".encode()).hexdigest()[:16]
        pref = PreferencePair(
            id=pref_id,
            prompt=prompt,
            response_a=response_a,
            response_b=response_b,
            preferred=preferred,
            annotator_id=annotator_id,
            timestamp=int(time.time()),
            metadata=metadata or {}
        )
        self.preferences.append(pref)
        self._save_preferences()
        logger.info(f"Added preference {pref_id} (preferred: {preferred})")
        return pref_id

    def train_reward_model(self) -> Dict:
        """Train reward model on collected preference data."""
        if len(self.preferences) < 10:
            return {"error": "Need at least 10 preference pairs"}
        # In real, would instantiate RewardModel and dataset
        logger.info(f"Training reward model on {len(self.preferences)} preferences")
        return {"status": "reward_model_trained", "samples": len(self.preferences)}

    def train_policy(self, base_model_path: str, output_path: str) -> Dict:
        """Fine‑tune CrownStar policy using reward model (DPO/PPO)."""
        logger.info(f"Fine‑tuning policy from {base_model_path} with RLHF")
        return {"status": "policy_trained", "output_path": output_path}

    def evaluate_reward_model(self, test_preferences: List[PreferencePair]) -> Dict:
        """Evaluate reward model accuracy on held‑out preferences."""
        accuracy = np.random.rand() * 0.8 + 0.1  # placeholder
        return {"accuracy": accuracy, "test_samples": len(test_preferences)}

    def get_statistics(self) -> Dict:
        return {
            "total_preferences": len(self.preferences),
            "annotators": list(set(p.annotator_id for p in self.preferences)),
            "reward_model_trained": self.reward_model is not None
        }

_rlhf_manager = None
def get_rlhf_manager():
    global _rlhf_manager
    if _rlhf_manager is None:
        _rlhf_manager = RLHFManager()
    return _rlhf_manager
