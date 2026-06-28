# security_model/core.py – CrownStar Model Security & Adversarial Defence Engine
import os, json, time, hashlib, base64, struct, logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Adversarial Attacks & Robustness
# --------------------------------------------------------------------
@dataclass
class AttackResult:
    attack_name: str
    success: bool
    original_accuracy: float
    adversarial_accuracy: float
    perturbation_norm: float
    time_ms: float

class AdversarialDefence:
    def __init__(self, model: nn.Module, device: str = "cpu"):
        self.model = model
        self.device = device
        self.model.to(device)
        self.model.eval()

    def fgsm_attack(self, images: torch.Tensor, labels: torch.Tensor, epsilon: float = 0.03) -> torch.Tensor:
        """Fast Gradient Sign Method."""
        images.requires_grad = True
        outputs = self.model(images)
        loss = F.cross_entropy(outputs, labels)
        self.model.zero_grad()
        loss.backward()
        sign_data_grad = images.grad.sign()
        adv_images = images + epsilon * sign_data_grad
        adv_images = torch.clamp(adv_images, 0, 1)
        return adv_images.detach()

    def pgd_attack(self, images: torch.Tensor, labels: torch.Tensor, epsilon: float = 0.03,
                   alpha: float = 0.01, iters: int = 40) -> torch.Tensor:
        """Projected Gradient Descent."""
        adv_images = images.clone().detach()
        for _ in range(iters):
            adv_images.requires_grad = True
            outputs = self.model(adv_images)
            loss = F.cross_entropy(outputs, labels)
            self.model.zero_grad()
            loss.backward()
            grad = adv_images.grad.sign()
            adv_images = adv_images + alpha * grad
            eta = torch.clamp(adv_images - images, min=-epsilon, max=epsilon)
            adv_images = torch.clamp(images + eta, 0, 1).detach()
        return adv_images

    def evaluate_robustness(self, test_loader, attack_name: str = "fgsm", epsilon: float = 0.03) -> AttackResult:
        """Evaluate model accuracy under attack."""
        start = time.perf_counter()
        correct_clean = 0
        correct_adv = 0
        total = 0
        perturbation_norm = 0.0
        for images, labels in test_loader:
            images, labels = images.to(self.device), labels.to(self.device)
            # Clean accuracy
            outputs = self.model(images)
            _, pred = torch.max(outputs, 1)
            correct_clean += (pred == labels).sum().item()
            # Adversarial attack
            if attack_name == "fgsm":
                adv_images = self.fgsm_attack(images, labels, epsilon)
            else:
                adv_images = self.pgd_attack(images, labels, epsilon)
            adv_outputs = self.model(adv_images)
            _, adv_pred = torch.max(adv_outputs, 1)
            correct_adv += (adv_pred == labels).sum().item()
            total += labels.size(0)
            perturbation_norm += torch.norm(adv_images - images).item()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return AttackResult(
            attack_name=attack_name,
            success=False,  # not used
            original_accuracy=correct_clean / total,
            adversarial_accuracy=correct_adv / total,
            perturbation_norm=perturbation_norm / len(test_loader),
            time_ms=elapsed_ms
        )

    def randomized_smoothing(self, images: torch.Tensor, num_samples: int = 100, sigma: float = 0.25) -> Tuple[int, float]:
        """Certified robustness via randomised smoothing."""
        predictions = []
        for _ in range(num_samples):
            noise = torch.randn_like(images) * sigma
            noisy = images + noise
            output = self.model(noisy)
            pred = output.argmax(dim=1).item()
            predictions.append(pred)
        majority_vote = max(set(predictions), key=predictions.count)
        confidence = predictions.count(majority_vote) / num_samples
        return majority_vote, confidence

# --------------------------------------------------------------------
# Model Watermarking (IP Protection)
# --------------------------------------------------------------------
@dataclass
class Watermark:
    key: str
    signature: str
    embedded_layer: str
    verification_threshold: float = 0.95

class ModelWatermark:
    """Embed a unique signature into model weights without harming performance."""
    def __init__(self, model: nn.Module):
        self.model = model

    def embed(self, secret: str, layer_name: str = "fc.weight", strength: float = 0.01) -> Watermark:
        """Embed watermark by adjusting weight statistics."""
        layer = dict(self.model.named_parameters())[layer_name]
        if layer is None:
            raise ValueError(f"Layer {layer_name} not found")
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        # Convert secret to target mean value
        target_mean = (int(secret_hash[:8], 16) % 100) / 100.0  # between 0 and 1
        with torch.no_grad():
            current_mean = layer.mean().item()
            adjustment = (target_mean - current_mean) * strength
            layer.add_(adjustment)
        return Watermark(
            key=layer_name,
            signature=secret_hash,
            embedded_layer=layer_name,
            verification_threshold=0.95
        )

    def verify(self, watermark: Watermark, secret: str) -> bool:
        """Verify watermark presence."""
        layer = dict(self.model.named_parameters()).get(watermark.embedded_layer)
        if layer is None:
            return False
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        if secret_hash != watermark.signature:
            return False
        # Check mean is still close to target
        target_mean = (int(secret_hash[:8], 16) % 100) / 100.0
        current_mean = layer.mean().item()
        similarity = 1.0 - abs(current_mean - target_mean) / target_mean if target_mean > 0 else 1.0
        return similarity > watermark.verification_threshold

# --------------------------------------------------------------------
# Encrypted Model Storage (AES‑GCM)
# --------------------------------------------------------------------
class EncryptedModelStore:
    """Encrypt model state dicts using AES‑GCM (via cryptography)."""
    def __init__(self, key: Optional[bytes] = None):
        self.key = key or os.urandom(32)
        self._init_crypto()

    def _init_crypto(self):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            self.crypto_available = True
        except ImportError:
            self.crypto_available = False
            logger.warning("cryptography not installed, encryption disabled")

    def encrypt_model(self, model_state_dict: Dict, output_path: str) -> str:
        """Encrypt and save model state dict."""
        if not self.crypto_available:
            raise ImportError("cryptography required for encryption")
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        import pickle
        data = pickle.dumps(model_state_dict)
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        with open(output_path, 'wb') as f:
            f.write(iv + encryptor.tag + ciphertext)
        return output_path

    def decrypt_model(self, encrypted_path: str) -> Dict:
        """Load and decrypt model state dict."""
        if not self.crypto_available:
            raise ImportError("cryptography required for decryption")
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        import pickle
        with open(encrypted_path, 'rb') as f:
            data = f.read()
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return pickle.loads(plaintext)

# --------------------------------------------------------------------
# Model Poisoning Detection & Robust Aggregation
# --------------------------------------------------------------------
class RobustAggregator:
    """Defences against Byzantine clients in federated learning."""
    @staticmethod
    def trimmed_mean(updates: List[torch.Tensor], trim_ratio: float = 0.3) -> torch.Tensor:
        """Remove largest and smallest values, average the rest."""
        k = int(len(updates) * trim_ratio)
        sorted_updates = torch.stack(updates).sort(dim=0).values
        trimmed = sorted_updates[k:-k] if k > 0 else sorted_updates
        return trimmed.mean(dim=0)

    @staticmethod
    def krum(updates: List[torch.Tensor], num_selected: int = 1) -> torch.Tensor:
        """Select update with smallest sum of distances to others."""
        distances = torch.cdist(torch.stack(updates), torch.stack(updates))
        scores = distances.sum(dim=1)
        best_idx = torch.argmin(scores)
        return updates[best_idx]

    @staticmethod
    def geometric_median(updates: List[torch.Tensor], eps: float = 1e-5) -> torch.Tensor:
        """Geometric median (robust to outliers)."""
        x = torch.stack(updates).mean(dim=0)
        for _ in range(100):
            weights = 1.0 / (torch.norm(torch.stack(updates) - x, dim=1) + eps)
            x = (weights.unsqueeze(1) * torch.stack(updates)).sum(dim=0) / weights.sum()
        return x

    @staticmethod
    def zscore_filter(updates: List[torch.Tensor], threshold: float = 2.0) -> List[torch.Tensor]:
        """Remove updates with Z‑score > threshold."""
        stacked = torch.stack(updates)
        mean = stacked.mean(dim=0)
        std = stacked.std(dim=0) + 1e-8
        zscores = torch.abs((stacked - mean) / std).max(dim=1).values
        return [u for i, u in enumerate(updates) if zscores[i] <= threshold]

# --------------------------------------------------------------------
# Security Manager (orchestrator)
# --------------------------------------------------------------------
class ModelSecurityManager:
    def __init__(self, config_path="config/security_model/config.json"):
        self.config = self._load_config(config_path)
        self.watermark = None
        self.encrypted_store = EncryptedModelStore()

    def _load_config(self, path):
        default = {
            "adversarial": {"epsilon": 0.03, "attack": "fgsm"},
            "watermark": {"default_layer": "fc.weight", "strength": 0.01},
            "encryption": {"key_env_var": "CROWNSTAR_MODEL_KEY"},
            "poison": {"aggregator": "trimmed_mean", "trim_ratio": 0.3}
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def evaluate_robustness(self, model: nn.Module, test_loader, attack: str = "fgsm") -> AttackResult:
        defence = AdversarialDefence(model)
        return defence.evaluate_robustness(test_loader, attack, self.config["adversarial"]["epsilon"])

    def embed_watermark(self, model: nn.Module, secret: str) -> Watermark:
        wm = ModelWatermark(model)
        self.watermark = wm.embed(secret, self.config["watermark"]["default_layer"], self.config["watermark"]["strength"])
        return self.watermark

    def verify_watermark(self, model: nn.Module, watermark: Watermark, secret: str) -> bool:
        wm = ModelWatermark(model)
        return wm.verify(watermark, secret)

    def encrypt_model(self, state_dict: Dict, output_path: str) -> str:
        return self.encrypted_store.encrypt_model(state_dict, output_path)

    def decrypt_model(self, encrypted_path: str) -> Dict:
        return self.encrypted_store.decrypt_model(encrypted_path)

    def robust_aggregate(self, updates: List[torch.Tensor]) -> torch.Tensor:
        method = self.config["poison"]["aggregator"]
        if method == "trimmed_mean":
            return RobustAggregator.trimmed_mean(updates, self.config["poison"]["trim_ratio"])
        elif method == "krum":
            return RobustAggregator.krum(updates)
        elif method == "geometric_median":
            return RobustAggregator.geometric_median(updates)
        else:
            return torch.stack(updates).mean(dim=0)

_sec_manager = None
def get_sec_manager():
    global _sec_manager
    if _sec_manager is None:
        _sec_manager = ModelSecurityManager()
    return _sec_manager
