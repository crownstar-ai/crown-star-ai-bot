# compression/core.py – CrownStar Model Compression & Distillation Engine
import os, json, time, shutil, tempfile
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Quantisation
# --------------------------------------------------------------------
@dataclass
class QuantisationConfig:
    dtype: str = "int8"           # int8, fp16, mixed
    calibration_method: str = "max"  # max, histogram, percentile
    per_channel: bool = True
    symmetric: bool = True
    backend: str = "fbgemm"       # fbgemm, qnnpack

class QuantisationEngine:
    """Post‑training quantisation with calibration."""
    def __init__(self, config: QuantisationConfig = None):
        self.config = config or QuantisationConfig()
        self.quantized_model = None

    def quantize_static(self, model: nn.Module, calibration_loader: torch.utils.data.DataLoader,
                        num_calibration_batches: int = 10) -> nn.Module:
        """
        Static quantisation: insert quant/dequant stubs, calibrate, convert.
        """
        model.eval()
        model.cpu()
        # Set qconfig
        if self.config.backend == "fbgemm":
            model.qconfig = torch.quantization.get_default_qconfig('fbgemm')
        else:
            model.qconfig = torch.quantization.get_default_qconfig('qnnpack')
        # Prepare
        model_prepared = torch.quantization.prepare(model, inplace=False)
        # Calibrate
        with torch.no_grad():
            for i, (inputs, _) in enumerate(calibration_loader):
                if i >= num_calibration_batches:
                    break
                model_prepared(inputs)
        # Convert
        quantized_model = torch.quantization.convert(model_prepared, inplace=False)
        self.quantized_model = quantized_model
        logger.info(f"Static quantisation complete: {self.config.dtype}")
        return quantized_model

    def quantize_dynamic(self, model: nn.Module, dtype: torch.dtype = torch.qint8) -> nn.Module:
        """Dynamic quantisation (weights only)."""
        model.eval()
        quantized_model = torch.quantization.quantize_dynamic(model, {nn.Linear, nn.LSTM}, dtype=dtype)
        self.quantized_model = quantized_model
        logger.info("Dynamic quantisation applied")
        return quantized_model

    def convert_to_fp16(self, model: nn.Module) -> nn.Module:
        """Half precision conversion for GPU inference."""
        model = model.half()
        logger.info("Converted to FP16")
        return model

# --------------------------------------------------------------------
# Pruning
# --------------------------------------------------------------------
@dataclass
class PruningConfig:
    method: str = "magnitude"   # magnitude, l1, structured, random
    sparsity: float = 0.3       # target sparsity (0-1)
    prune_heads: bool = False
    prune_embeddings: bool = False
    regrowth: bool = False      # iterative pruning with regrowth (RigL)

class PruningEngine:
    def __init__(self, config: PruningConfig = None):
        self.config = config or PruningConfig()

    def magnitude_prune(self, model: nn.Module) -> nn.Module:
        """Global magnitude pruning: remove smallest weights."""
        parameters_to_prune = []
        for name, module in model.named_modules():
            if isinstance(module, nn.Linear) or isinstance(module, nn.Conv2d):
                parameters_to_prune.append((module, 'weight'))
        torch.nn.utils.prune.global_unstructured(
            parameters_to_prune,
            pruning_method=torch.nn.utils.prune.L1Unstructured,
            amount=self.config.sparsity
        )
        # Remove pruning masks (make permanent)
        for module, name in parameters_to_prune:
            torch.nn.utils.prune.remove(module, name)
        logger.info(f"Magnitude pruning applied: {self.config.sparsity*100:.0f}% sparsity")
        return model

    def structured_prune_channels(self, model: nn.Module) -> nn.Module:
        """Channel pruning for Conv2d layers (simplified)."""
        # In full implementation, would use torch.nn.utils.prune.ln_structured
        # For demonstration, we use L1 unstructured as placeholder
        return self.magnitude_prune(model)

    def iterative_prune(self, model: nn.Module, trainer_fn: Callable, epochs: int = 5) -> nn.Module:
        """Iterative pruning with fine‑tuning between stages."""
        target_sparsity = self.config.sparsity
        current_sparsity = 0.0
        stages = 5
        for stage in range(stages):
            stage_sparsity = target_sparsity * (stage + 1) / stages
            # Apply pruning
            self.config.sparsity = stage_sparsity
            model = self.magnitude_prune(model)
            # Fine‑tune for a few epochs
            trainer_fn(model, epochs=1)
        self.config.sparsity = target_sparsity
        return model

# --------------------------------------------------------------------
# Knowledge Distillation
# --------------------------------------------------------------------
@dataclass
class DistillationConfig:
    temperature: float = 4.0
    alpha: float = 0.7           # weight for distillation loss (1-alpha for student CE)
    hint_layer: Optional[str] = None  # intermediate layer matching
    teacher_model_path: Optional[str] = None

class DistillationEngine:
    def __init__(self, config: DistillationConfig = None):
        self.config = config or DistillationConfig()
        self.teacher: Optional[nn.Module] = None

    def load_teacher(self, teacher_model: nn.Module):
        self.teacher = teacher_model
        self.teacher.eval()

    def distillation_loss(self, student_logits, teacher_logits, labels, temperature, alpha):
        """KD loss = alpha * soft_target_loss + (1-alpha) * hard_label_loss"""
        soft_targets = F.softmax(teacher_logits / temperature, dim=1)
        soft_prob = F.log_softmax(student_logits / temperature, dim=1)
        soft_loss = F.kl_div(soft_prob, soft_targets, reduction='batchmean') * (temperature ** 2)
        hard_loss = F.cross_entropy(student_logits, labels)
        return alpha * soft_loss + (1 - alpha) * hard_loss

    def train_student(self, student: nn.Module, train_loader, val_loader, epochs: int = 5,
                      lr: float = 1e-4, device="cpu") -> Dict:
        """Train student model with teacher supervision."""
        if self.teacher is None:
            raise ValueError("Teacher model not loaded")
        student.to(device)
        self.teacher.to(device)
        optimizer = torch.optim.AdamW(student.parameters(), lr=lr)
        student.train()
        history = {"train_loss": [], "val_acc": []}
        for epoch in range(epochs):
            total_loss = 0.0
            for batch_idx, (inputs, labels) in enumerate(train_loader):
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer.zero_grad()
                student_logits = student(inputs)
                with torch.no_grad():
                    teacher_logits = self.teacher(inputs)
                loss = self.distillation_loss(student_logits, teacher_logits, labels,
                                              self.config.temperature, self.config.alpha)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            avg_loss = total_loss / len(train_loader)
            history["train_loss"].append(avg_loss)
            # Validation
            acc = self.evaluate(student, val_loader, device)
            history["val_acc"].append(acc)
            logger.info(f"Epoch {epoch+1}: loss={avg_loss:.4f}, val_acc={acc:.4f}")
        return history

    def evaluate(self, model: nn.Module, val_loader, device="cpu") -> float:
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                _, predicted = torch.max(outputs, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        return correct / total

# --------------------------------------------------------------------
# Compression Manager (orchestrates quantisation, pruning, distillation)
# --------------------------------------------------------------------
class CompressionManager:
    def __init__(self, config_path="config/compression/config.json"):
        self.config = self._load_config(config_path)
        self.quant_engine = QuantisationEngine(QuantisationConfig(**self.config.get("quantisation", {})))
        self.prune_engine = PruningEngine(PruningConfig(**self.config.get("pruning", {})))
        self.distill_engine = DistillationEngine(DistillationConfig(**self.config.get("distillation", {})))

    def _load_config(self, path):
        default = {
            "quantisation": {"dtype": "int8", "calibration_method": "max", "per_channel": True},
            "pruning": {"method": "magnitude", "sparsity": 0.3, "prune_heads": False},
            "distillation": {"temperature": 4.0, "alpha": 0.7},
            "benchmark": {"batch_size": 32, "num_iterations": 100}
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def quantize_model(self, model: nn.Module, calibration_loader=None, dynamic=False) -> nn.Module:
        if dynamic:
            return self.quant_engine.quantize_dynamic(model)
        else:
            if calibration_loader is None:
                raise ValueError("Calibration loader required for static quantisation")
            return self.quant_engine.quantize_static(model, calibration_loader)

    def prune_model(self, model: nn.Module, iterative: bool = False, trainer_fn=None) -> nn.Module:
        if iterative and trainer_fn:
            return self.prune_engine.iterative_prune(model, trainer_fn)
        else:
            return self.prune_engine.magnitude_prune(model)

    def distill_model(self, teacher: nn.Module, student: nn.Module, train_loader, val_loader,
                      epochs: int = 5) -> Dict:
        self.distill_engine.load_teacher(teacher)
        return self.distill_engine.train_student(student, train_loader, val_loader, epochs)

    def benchmark_model(self, model: nn.Module, test_loader, device="cpu") -> Dict:
        """Measure inference speed and memory usage."""
        model.to(device)
        model.eval()
        # Warm up
        for _ in range(10):
            for inputs, _ in test_loader:
                inputs = inputs.to(device)
                _ = model(inputs)
                break
        # Measure latency
        import time
        latencies = []
        with torch.no_grad():
            for i, (inputs, _) in enumerate(test_loader):
                if i >= self.config["benchmark"]["num_iterations"]:
                    break
                inputs = inputs.to(device)
                start = time.perf_counter()
                _ = model(inputs)
                end = time.perf_counter()
                latencies.append((end - start) * 1000)
        # Memory usage (peak)
        import psutil
        mem_mb = psutil.Process().memory_info().rss / 1024**2
        return {
            "latency_ms_mean": np.mean(latencies),
            "latency_ms_std": np.std(latencies),
            "memory_mb": mem_mb,
            "device": str(device)
        }

_comp_manager = None
def get_comp_manager():
    global _comp_manager
    if _comp_manager is None:
        _comp_manager = CompressionManager()
    return _comp_manager
