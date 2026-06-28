# ====================================================================================================
# distillation.py – Knowledge distillation for CrownStar‑Absolute
# Features:
#   - Distill large teacher model (Pro/Enterprise) into smaller student model (Free/Basic)
#   - Multiple distillation losses: KL divergence, MSE, cosine, attention transfer
#   - Temperature‑aware distillation (Hinton, 2015)
#   - Progressive distillation (student learns from intermediate representations)
#   - Data‑free distillation (generate synthetic data from teacher)
#   - Integration with CrownStarCore training pipeline
#   - Tier‑specific distilled models (free.pt, basic.pt, pro.pt, enterprise.pt)
# ====================================================================================================

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import numpy as np
import random
import math
import time
from typing import Optional, Dict, List, Tuple, Callable, Any, Union
from pathlib import Path
import logging
import copy

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# 1. Core Distillation Losses
# --------------------------------------------------------------------
class DistillationLoss(nn.Module):
    """
    Combined distillation loss: KL divergence between teacher and student logits,
    plus optional cross‑entropy with hard labels.
    
    L = α * L_soft + (1-α) * L_hard
    where L_soft = KL(softmax(logits_teacher / τ) || softmax(logits_student / τ)) * τ²
    """
    
    def __init__(self, temperature: float = 4.0, alpha: float = 0.7, 
                 reduction: str = 'batchmean'):
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha
        self.reduction = reduction
        self.kl_loss = nn.KLDivLoss(reduction=reduction)
        self.ce_loss = nn.CrossEntropyLoss()
    
    def forward(self, student_logits: torch.Tensor, teacher_logits: torch.Tensor,
                labels: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            student_logits: Logits from student model (N, C)
            teacher_logits: Logits from teacher model (N, C)
            labels: Optional hard labels (N,)
        """
        # Soft targets distillation (KL divergence)
        student_soft = F.log_softmax(student_logits / self.temperature, dim=-1)
        teacher_soft = F.softmax(teacher_logits / self.temperature, dim=-1)
        kl_loss = self.kl_loss(student_soft, teacher_soft) * (self.temperature ** 2)
        
        loss = self.alpha * kl_loss
        
        # Hard targets cross‑entropy (if labels provided)
        if labels is not None:
            ce_loss = self.ce_loss(student_logits, labels)
            loss = loss + (1 - self.alpha) * ce_loss
        
        return loss

class AttentionTransferLoss(nn.Module):
    """
    Attention transfer loss – align attention maps between teacher and student.
    Useful for transformer‑based models.
    """
    
    def __init__(self, p: int = 2):
        super().__init__()
        self.p = p
    
    def forward(self, student_attentions: List[torch.Tensor], 
                teacher_attentions: List[torch.Tensor]) -> torch.Tensor:
        """
        Args:
            student_attentions: List of attention maps from student (each shape [B, H, L, L])
            teacher_attentions: List from teacher (same shape)
        """
        if len(student_attentions) != len(teacher_attentions):
            raise ValueError("Number of attention layers must match")
        
        total_loss = 0.0
        for s_attn, t_attn in zip(student_attentions, teacher_attentions):
            # Normalise across heads
            s_attn = s_attn / (s_attn.sum(dim=-1, keepdim=True) + 1e-8)
            t_attn = t_attn / (t_attn.sum(dim=-1, keepdim=True) + 1e-8)
            # MSE loss between attention matrices
            loss = F.mse_loss(s_attn, t_attn)
            total_loss += loss
        
        return total_loss / len(student_attentions)

class FeatureMapTransferLoss(nn.Module):
    """
    Transfer intermediate feature maps (e.g., for CNN or MLP).
    """
    
    def __init__(self, norm: str = 'l2'):
        super().__init__()
        self.norm = norm
    
    def forward(self, student_features: List[torch.Tensor], 
                teacher_features: List[torch.Tensor]) -> torch.Tensor:
        total_loss = 0.0
        for s_f, t_f in zip(student_features, teacher_features):
            # Normalise to same spatial dimensions if needed
            if s_f.shape != t_f.shape:
                # Adaptive pooling to match teacher shape
                s_f = F.interpolate(s_f, size=t_f.shape[-2:], mode='bilinear', align_corners=False)
            if self.norm == 'l2':
                loss = F.mse_loss(s_f, t_f)
            elif self.norm == 'cosine':
                s_f = s_f.view(s_f.size(0), -1)
                t_f = t_f.view(t_f.size(0), -1)
                loss = 1 - F.cosine_similarity(s_f, t_f).mean()
            total_loss += loss
        return total_loss / len(student_features)

# --------------------------------------------------------------------
# 2. Distillation Trainer
# --------------------------------------------------------------------
class DistillationTrainer:
    """
    Complete distillation pipeline: train student model from teacher.
    """
    
    def __init__(self, teacher_model: nn.Module, student_model: nn.Module,
                 temperature: float = 4.0, alpha: float = 0.7,
                 use_attention: bool = False, use_features: bool = False,
                 device: str = 'cuda' if torch.cuda.is_available() else 'cpu'):
        """
        Args:
            teacher_model: Pre‑trained larger model
            student_model: Smaller model to be distilled
            temperature: Softmax temperature for distillation
            alpha: Weight for soft loss vs hard loss
            use_attention: If True, also align attention maps
            use_features: If True, also align intermediate features
            device: Device to run on
        """
        self.teacher = teacher_model.to(device).eval()
        self.student = student_model.to(device).train()
        self.temperature = temperature
        self.alpha = alpha
        self.use_attention = use_attention
        self.use_features = use_features
        self.device = device
        
        self.distill_loss = DistillationLoss(temperature, alpha)
        if use_attention:
            self.attn_loss = AttentionTransferLoss()
        if use_features:
            self.feature_loss = FeatureMapTransferLoss()
    
    def _get_teacher_logits_and_features(self, inputs: torch.Tensor):
        """Forward pass through teacher, capturing attention and features if needed."""
        if self.use_attention or self.use_features:
            # Hook into teacher layers – requires model to expose intermediate outputs
            # For simplicity, assume teacher.forward returns (logits, attentions, features)
            # Placeholder: if teacher has a method `forward_with_intermediates`
            if hasattr(self.teacher, 'forward_with_intermediates'):
                return self.teacher.forward_with_intermediates(inputs)
            else:
                with torch.no_grad():
                    logits = self.teacher(inputs)
                return logits, None, None
        else:
            with torch.no_grad():
                logits = self.teacher(inputs)
            return logits, None, None
    
    def train_step(self, inputs: torch.Tensor, labels: Optional[torch.Tensor] = None,
                   optimizer: torch.optim.Optimizer = None) -> torch.Tensor:
        """Single training step."""
        self.student.train()
        teacher_logits, teacher_attns, teacher_features = self._get_teacher_logits_and_features(inputs)
        student_logits = self.student(inputs)
        
        loss = self.distill_loss(student_logits, teacher_logits, labels)
        
        if self.use_attention and teacher_attns is not None:
            # Need to also capture student attention maps
            student_attns = self.student.get_attention_maps() if hasattr(self.student, 'get_attention_maps') else None
            if student_attns is not None:
                loss = loss + self.attn_loss(student_attns, teacher_attns)
        
        if self.use_features and teacher_features is not None:
            student_features = self.student.get_intermediate_features() if hasattr(self.student, 'get_intermediate_features') else None
            if student_features is not None:
                loss = loss + self.feature_loss(student_features, teacher_features)
        
        if optimizer:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        
        return loss
    
    def train_epoch(self, dataloader: DataLoader, optimizer: torch.optim.Optimizer,
                    progress_callback: Optional[Callable] = None) -> float:
        """Train for one full epoch."""
        total_loss = 0.0
        num_batches = 0
        
        for batch in dataloader:
            if isinstance(batch, (tuple, list)):
                inputs = batch[0].to(self.device)
                labels = batch[1].to(self.device) if len(batch) > 1 else None
            else:
                inputs = batch.to(self.device)
                labels = None
            
            loss = self.train_step(inputs, labels, optimizer)
            total_loss += loss.item()
            num_batches += 1
            
            if progress_callback:
                progress_callback(loss.item(), num_batches)
        
        return total_loss / num_batches
    
    def distill(self, dataloader: DataLoader, epochs: int = 10, 
                lr: float = 1e-4, weight_decay: float = 1e-5,
                save_path: Optional[str] = None) -> Dict[str, List[float]]:
        """Complete distillation process."""
        optimizer = optim.AdamW(self.student.parameters(), lr=lr, weight_decay=weight_decay)
        history = {"loss": []}
        
        for epoch in range(epochs):
            avg_loss = self.train_epoch(dataloader, optimizer)
            history["loss"].append(avg_loss)
            logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")
            
            if save_path and (epoch + 1) % 5 == 0:
                torch.save(self.student.state_dict(), f"{save_path}_epoch{epoch+1}.pt")
        
        if save_path:
            torch.save(self.student.state_dict(), f"{save_path}_final.pt")
            logger.info(f"Distilled student model saved to {save_path}_final.pt")
        
        return history

# --------------------------------------------------------------------
# 3. Data‑Free Distillation (using synthetic data)
# --------------------------------------------------------------------
class DataFreeDistillation:
    """
    Distillation without real data – generate synthetic samples from teacher.
    Uses techniques from "Data‑Free Knowledge Distillation" (Lopes et al., 2017).
    """
    
    def __init__(self, teacher_model: nn.Module, student_model: nn.Module,
                 input_shape: Tuple[int, ...], latent_dim: int = 256,
                 device: str = 'cuda' if torch.cuda.is_available() else 'cpu'):
        self.teacher = teacher_model.to(device).eval()
        self.student = student_model.to(device).train()
        self.input_shape = input_shape
        self.latent_dim = latent_dim
        self.device = device
        
        # Generator for synthetic data
        self.generator = nn.Sequential(
            nn.Linear(latent_dim, 512),
            nn.ReLU(),
            nn.Linear(512, 1024),
            nn.ReLU(),
            nn.Linear(1024, int(np.prod(input_shape))),
            nn.Tanh()
        ).to(device)
        
        self.distill_loss = DistillationLoss(temperature=4.0)
    
    def generate_batch(self, batch_size: int) -> torch.Tensor:
        """Generate synthetic input batch from random noise."""
        z = torch.randn(batch_size, self.latent_dim, device=self.device)
        synthetic = self.generator(z)
        synthetic = synthetic.view(batch_size, *self.input_shape)
        return synthetic
    
    def train_step(self, optimizer_g: torch.optim.Optimizer,
                   optimizer_s: torch.optim.Optimizer) -> Tuple[float, float]:
        """One step of generator + student training."""
        batch_size = 32
        synthetic = self.generate_batch(batch_size)
        
        # Generator wants to maximise teacher confidence (or minimise entropy)
        teacher_logits = self.teacher(synthetic)
        teacher_probs = F.softmax(teacher_logits, dim=-1)
        # Generator loss: maximise entropy of teacher predictions (encourage diversity)
        entropy = -(teacher_probs * torch.log(teacher_probs + 1e-8)).sum(dim=-1).mean()
        loss_g = -entropy  # we want high entropy
        
        optimizer_g.zero_grad()
        loss_g.backward()
        optimizer_g.step()
        
        # Distillation loss on student
        student_logits = self.student(synthetic)
        loss_s = self.distill_loss(student_logits, teacher_logits, None)
        
        optimizer_s.zero_grad()
        loss_s.backward()
        optimizer_s.step()
        
        return loss_g.item(), loss_s.item()
    
    def distill(self, steps: int = 10000, save_path: Optional[str] = None) -> Dict[str, List[float]]:
        """Run data‑free distillation for a number of steps."""
        optimizer_g = optim.Adam(self.generator.parameters(), lr=1e-3)
        optimizer_s = optim.Adam(self.student.parameters(), lr=1e-4)
        history = {"loss_g": [], "loss_s": []}
        
        for step in range(steps):
            loss_g, loss_s = self.train_step(optimizer_g, optimizer_s)
            history["loss_g"].append(loss_g)
            history["loss_s"].append(loss_s)
            if step % 100 == 0:
                logger.info(f"Step {step}/{steps}, G loss: {loss_g:.4f}, S loss: {loss_s:.4f}")
            if save_path and step % 1000 == 0:
                torch.save(self.student.state_dict(), f"{save_path}_step{step}.pt")
        
        if save_path:
            torch.save(self.student.state_dict(), f"{save_path}_final.pt")
        return history

# --------------------------------------------------------------------
# 4. Progressive Distillation (layer‑by‑layer)
# --------------------------------------------------------------------
class ProgressiveDistillation:
    """
    Distill teacher into student layer by layer.
    First align output, then freeze and distill internal representations.
    """
    
    def __init__(self, teacher: nn.Module, student: nn.Module, 
                 device: str = 'cuda' if torch.cuda.is_available() else 'cpu'):
        self.teacher = teacher.to(device).eval()
        self.student = student.to(device).train()
        self.device = device
    
    def distill_output(self, dataloader: DataLoader, epochs: int = 5, lr: float = 1e-4) -> None:
        """First stage: distill only final outputs."""
        optimizer = optim.AdamW(self.student.parameters(), lr=lr)
        loss_fn = DistillationLoss(temperature=2.0, alpha=0.5)
        
        for epoch in range(epochs):
            total_loss = 0.0
            for batch in dataloader:
                inputs = batch[0].to(self.device)
                with torch.no_grad():
                    teacher_logits = self.teacher(inputs)
                student_logits = self.student(inputs)
                loss = loss_fn(student_logits, teacher_logits, None)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            logger.info(f"Output distillation epoch {epoch+1}, loss: {total_loss/len(dataloader):.4f}")
    
    def distill_features(self, dataloader: DataLoader, epochs: int = 5, lr: float = 1e-4) -> None:
        """Second stage: align internal features (requires access to intermediate representations)."""
        # Simplified: assume both models have a method `get_penultimate_features`
        optimizer = optim.AdamW(self.student.parameters(), lr=lr)
        
        for epoch in range(epochs):
            total_loss = 0.0
            for batch in dataloader:
                inputs = batch[0].to(self.device)
                with torch.no_grad():
                    teacher_features = self.teacher.get_penultimate_features(inputs)
                student_features = self.student.get_penultimate_features(inputs)
                loss = F.mse_loss(student_features, teacher_features)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            logger.info(f"Feature distillation epoch {epoch+1}, loss: {total_loss/len(dataloader):.4f}")

# --------------------------------------------------------------------
# 5. Distillation Wrapper for CrownStarCore
# --------------------------------------------------------------------
def create_distilled_model(teacher_path: str, student_model_class, student_config,
                           data_loader: DataLoader, epochs: int = 5,
                           output_path: str = "models/student_distilled.pt",
                           device: str = 'cuda' if torch.cuda.is_available() else 'cpu') -> nn.Module:
    """
    Convenience function to distill a teacher model into a new student model.
    
    Args:
        teacher_path: Path to pre‑trained teacher checkpoint
        student_model_class: Class of student model (e.g., UnifiedSuperModel)
        student_config: Configuration for student model
        data_loader: DataLoader for distillation (can be training data)
        epochs: Number of distillation epochs
        output_path: Where to save distilled student
        device: Computation device
    
    Returns:
        Distilled student model
    """
    # Load teacher
    teacher = student_model_class(student_config)  # same class but larger config
    # In reality, teacher would have different config; here we assume same class with larger hidden_dims
    teacher.load_state_dict(torch.load(teacher_path, map_location=device))
    teacher.to(device).eval()
    
    # Create student (smaller)
    student = student_model_class(student_config)
    student.to(device)
    
    trainer = DistillationTrainer(teacher, student, temperature=4.0, alpha=0.7, device=device)
    trainer.distill(data_loader, epochs=epochs, save_path=output_path.replace('.pt', ''))
    
    return student

def get_distilled_model_for_tier(tier: str, teacher_model: nn.Module, student_config) -> nn.Module:
    """
    Return appropriate distilled model based on tier.
    Free and Basic get distilled versions; Pro/Enterprise get original.
    """
    if tier in ("free", "basic"):
        logger.info(f"Using distilled student model for tier {tier}")
        # In practice, this would load a pre‑distilled checkpoint
        # For now, we return a shallow copy with reduced dimensions
        import copy
        student = copy.deepcopy(teacher_model)
        # Modify dimensions (simplified)
        for name, param in student.named_parameters():
            if 'weight' in name:
                # Reduce size (toy example)
                new_shape = (max(1, param.shape[0] // 4), max(1, param.shape[1] // 4))
                # Not actually feasible; placeholder
                pass
        return student
    else:
        return teacher_model

# --------------------------------------------------------------------
# 6. Example distillation of UnifiedSuperModel for Free/Basic tiers
# --------------------------------------------------------------------
def distill_unified_model(teacher_checkpoint: str, student_config: dict,
                          train_dataloader: DataLoader,
                          output_dir: str = "models/distilled") -> Dict[str, str]:
    """
    Distill the unified super‑model for Free and Basic tiers.
    Returns paths to the distilled models.
    """
    from src.core.crownstar_core import UnifiedSuperModel, UnifiedModelConfig
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load teacher (full model)
    teacher_config = UnifiedModelConfig(
        input_dim=768,
        hidden_dims=[1024, 2048, 4096, 2048, 1024],
        output_dim=50257
    )
    teacher = UnifiedSuperModel(teacher_config)
    teacher.load_state_dict(torch.load(teacher_checkpoint))
    
    # Student for Free tier (tiny)
    free_config = UnifiedModelConfig(
        input_dim=128,
        hidden_dims=[256, 128],
        output_dim=50257,
        transformer_layers=2,
        attention_heads=4
    )
    free_student = UnifiedSuperModel(free_config)
    
    # Distill Free
    logger.info("Distilling Free tier model...")
    free_trainer = DistillationTrainer(teacher, free_student, temperature=4.0, alpha=0.7)
    free_trainer.distill(train_dataloader, epochs=3, save_path=f"{output_dir}/free")
    
    # Student for Basic tier (small)
    basic_config = UnifiedModelConfig(
        input_dim=384,
        hidden_dims=[512, 256],
        output_dim=50257,
        transformer_layers=6,
        attention_heads=8
    )
    basic_student = UnifiedSuperModel(basic_config)
    basic_trainer = DistillationTrainer(teacher, basic_student, temperature=4.0, alpha=0.7)
    basic_trainer.distill(train_dataloader, epochs=5, save_path=f"{output_dir}/basic")
    
    return {
        "free": f"{output_dir}/free_final.pt",
        "basic": f"{output_dir}/basic_final.pt"
    }

# --------------------------------------------------------------------
# 7. Evaluation of Distilled Models
# --------------------------------------------------------------------
def evaluate_distilled_models(teacher_model: nn.Module, 
                               student_models: Dict[str, nn.Module],
                               test_loader: DataLoader,
                               device: str = 'cuda') -> Dict[str, float]:
    """
    Evaluate accuracy/loss of distilled models against teacher baseline.
    """
    teacher_model.eval()
    results = {"teacher": 0.0}
    criterion = nn.CrossEntropyLoss()
    
    # Teacher baseline
    teacher_loss = 0.0
    teacher_correct = 0
    total = 0
    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = teacher_model(inputs)
            loss = criterion(outputs, labels)
            teacher_loss += loss.item()
            pred = outputs.argmax(dim=1)
            teacher_correct += (pred == labels).sum().item()
            total += labels.size(0)
    results["teacher_loss"] = teacher_loss / len(test_loader)
    results["teacher_acc"] = teacher_correct / total
    
    for name, student in student_models.items():
        student.eval()
        student_loss = 0.0
        student_correct = 0
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = student(inputs)
                loss = criterion(outputs, labels)
                student_loss += loss.item()
                pred = outputs.argmax(dim=1)
                student_correct += (pred == labels).sum().item()
        results[f"{name}_loss"] = student_loss / len(test_loader)
        results[f"{name}_acc"] = student_correct / total
    
    return results

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Distill using training dataloader
teacher_path = "models/enterprise.pt"
train_loader = create_dataloader(train_files, tokenizer)
distilled_paths = distill_unified_model(teacher_path, student_config, train_loader)

# Load distilled model for Free tier
free_model = UnifiedSuperModel(free_config)
free_model.load_state_dict(torch.load(distilled_paths["free"]))

# Evaluate
results = evaluate_distilled_models(teacher, {"free": free_model}, test_loader)
print(f"Teacher acc: {results['teacher_acc']:.4f}, Free acc: {results['free_acc']:.4f}")
"""

# ====================================================================================================
# END OF distillation.py
# ====================================================================================================
