# ====================================================================================================
# quantization.py – Model quantization utilities for CrownStar‑Absolute
# Features:
#   - FP16 (half precision) conversion for faster inference on compatible GPUs
#   - INT8 dynamic quantization (CPU) for smaller memory footprint
#   - INT8 static quantization with calibration (for optimal performance)
#   - QAT (Quantization Aware Training) helpers
#   - Per‑layer configuration and selective quantization
#   - Integration with tier system: Free/Basic use quantized models, Pro/Enterprise use FP32
#   - ONNX export with quantization (optional)
# ====================================================================================================

import torch
import torch.nn as nn
import torch.quantization as quant
from torch.quantization import QuantStub, DeQuantStub
import numpy as np
from typing import Dict, Optional, Union, List, Tuple, Callable, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# 1. FP16 (Half Precision) Conversion
# --------------------------------------------------------------------
def convert_to_fp16(model: nn.Module, keep_original: bool = False) -> nn.Module:
    """
    Convert model parameters and buffers to FP16 (half precision).
    
    Args:
        model: PyTorch model
        keep_original: If True, returns a copy; otherwise modifies in‑place
    
    Returns:
        Model in FP16 (half)
    """
    if keep_original:
        import copy
        model = copy.deepcopy(model)
    model = model.half()
    logger.info("Model converted to FP16")
    return model

def convert_to_fp32(model: nn.Module) -> nn.Module:
    """Convert model back to FP32."""
    model = model.float()
    logger.info("Model converted to FP32")
    return model

def get_fp16_memory_reduction(model: nn.Module) -> float:
    """Estimate memory reduction when using FP16 (approx 50%)."""
    total_params = sum(p.numel() for p in model.parameters())
    fp32_bytes = total_params * 4
    fp16_bytes = total_params * 2
    reduction = (fp32_bytes - fp16_bytes) / fp32_bytes
    return reduction

# --------------------------------------------------------------------
# 2. Dynamic Quantization (INT8, CPU)
# --------------------------------------------------------------------
def apply_dynamic_quantization(model: nn.Module, 
                               qconfig_spec: Optional[Dict] = None,
                               dtype: torch.dtype = torch.qint8) -> nn.Module:
    """
    Apply dynamic quantization (weights quantized, activations remain FP32).
    Best for LSTM, Transformer, Linear layers.
    
    Args:
        model: PyTorch model
        qconfig_spec: Optional layer‑specific quantization configuration
        dtype: Quantized data type (default qint8)
    
    Returns:
        Quantized model (CPU only)
    """
    model = model.cpu()
    model.eval()
    
    # Default: quantise Linear and LSTM layers
    if qconfig_spec is None:
        qconfig_spec = {nn.Linear, nn.LSTM, nn.GRU, nn.RNN}
    
    quantized_model = torch.quantization.quantize_dynamic(
        model, qconfig_spec, dtype=dtype
    )
    logger.info(f"Dynamic quantization applied to {len(quantized_model.modules())} modules")
    return quantized_model

def apply_dynamic_quantization_for_tier(model: nn.Module, tier: str) -> nn.Module:
    """
    Apply dynamic quantization based on tier (Free/Basic use INT8, Pro/Enterprise use FP32).
    """
    if tier in ("free", "basic"):
        logger.info(f"Applying INT8 dynamic quantization for tier {tier}")
        return apply_dynamic_quantization(model)
    else:
        logger.info(f"Keeping FP32 for tier {tier}")
        return model

# --------------------------------------------------------------------
# 3. Static Quantization (INT8) with Calibration
# --------------------------------------------------------------------
class QuantizableWrapper:
    """
    Wrapper to prepare a model for static quantization with custom calibration.
    """
    def __init__(self, model: nn.Module, qconfig: Optional[torch.quantization.QConfig] = None):
        self.model = model
        if qconfig is None:
            # Default: per‑tensor affine for weights, per‑tensor for activations
            self.qconfig = torch.quantization.default_qconfig
        else:
            self.qconfig = qconfig
        self.model.qconfig = self.qconfig
        # Add QuantStub/DeQuantStub at entry/exit if not present
        self._add_stubs()
    
    def _add_stubs(self):
        """Add QuantStub and DeQuantStub to the model."""
        if not hasattr(self.model, 'quant'):
            self.model.quant = QuantStub()
        if not hasattr(self.model, 'dequant'):
            self.model.dequant = DeQuantStub()
        # Override forward to wrap with stubs
        original_forward = self.model.forward
        def quantized_forward(x):
            x = self.model.quant(x)
            x = original_forward(x)
            x = self.model.dequant(x)
            return x
        self.model.forward = quantized_forward
    
    def prepare(self, example_inputs: torch.Tensor):
        """Prepare model for calibration (insert observers)."""
        torch.quantization.prepare(self.model, inplace=True)
        # Run calibration with example inputs
        with torch.no_grad():
            self.model(example_inputs)
        logger.info("Model prepared for static quantization")
    
    def calibrate(self, calibration_loader: torch.utils.data.DataLoader, num_batches: int = 10):
        """
        Run calibration over a representative dataset.
        
        Args:
            calibration_loader: DataLoader providing calibration data
            num_batches: Number of batches to use for calibration
        """
        self.model.eval()
        with torch.no_grad():
            for i, (inputs, _) in enumerate(calibration_loader):
                if i >= num_batches:
                    break
                self.model(inputs)
        logger.info(f"Calibration completed with {num_batches} batches")
    
    def convert(self) -> nn.Module:
        """Convert prepared model to quantized version."""
        quantized_model = torch.quantization.convert(self.model, inplace=False)
        logger.info("Static quantization conversion complete")
        return quantized_model

def static_quantize(model: nn.Module, 
                    calibration_loader: torch.utils.data.DataLoader,
                    num_calibration_batches: int = 10,
                    qconfig: Optional[torch.quantization.QConfig] = None) -> nn.Module:
    """
    Full static quantization pipeline: prepare → calibrate → convert.
    
    Args:
        model: FP32 model (CPU)
        calibration_loader: DataLoader for representative input data
        num_calibration_batches: Number of batches for calibration
        qconfig: Quantization configuration (optional)
    
    Returns:
        Quantized INT8 model
    """
    model = model.cpu().eval()
    wrapper = QuantizableWrapper(model, qconfig)
    
    # Get example input
    example_inputs, _ = next(iter(calibration_loader))
    wrapper.prepare(example_inputs)
    wrapper.calibrate(calibration_loader, num_calibration_batches)
    quantized_model = wrapper.convert()
    return quantized_model

# --------------------------------------------------------------------
# 4. Quantization Aware Training (QAT)
# --------------------------------------------------------------------
class QATModel(nn.Module):
    """
    Wrapper for Quantization Aware Training.
    Use during fine‑tuning to preserve accuracy after quantisation.
    """
    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model
        # Set QAT configuration
        self.model.qconfig = torch.quantization.get_default_qat_qconfig('fbgemm')
        # Add stubs
        self.quant = QuantStub()
        self.dequant = DeQuantStub()
    
    def forward(self, x):
        x = self.quant(x)
        x = self.model(x)
        x = self.dequant(x)
        return x
    
    def prepare_qat(self):
        """Prepare model for QAT (inserts fake quantisation nodes)."""
        torch.quantization.prepare_qat(self.model, inplace=True)
    
    def convert(self) -> nn.Module:
        """Convert QAT model to quantized inference model."""
        return torch.quantization.convert(self.model, inplace=False)

def train_qat(model: nn.Module, train_loader, optimizer, epochs: int = 1):
    """
    Perform Quantization Aware Training.
    """
    qat_model = QATModel(model)
    qat_model.prepare_qat()
    qat_model.train()
    criterion = nn.CrossEntropyLoss()
    for epoch in range(epochs):
        for batch_idx, (data, target) in enumerate(train_loader):
            optimizer.zero_grad()
            output = qat_model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
    quantized_model = qat_model.convert()
    logger.info(f"QAT completed after {epochs} epochs")
    return quantized_model

# --------------------------------------------------------------------
# 5. Selective Quantization (per layer)
# --------------------------------------------------------------------
def selective_quantize(model: nn.Module, 
                       module_names: List[str],
                       quant_type: str = "dynamic") -> nn.Module:
    """
    Quantise only specific modules by name.
    
    Args:
        model: PyTorch model
        module_names: List of module names to quantize (e.g., ['mlp.0', 'transformer.2'])
        quant_type: 'dynamic' or 'static'
    
    Returns:
        Model with selected modules quantized
    """
    model = model.cpu()
    for name, module in model.named_modules():
        if name in module_names:
            if quant_type == "dynamic":
                torch.quantization.quantize_dynamic(module, {type(module)}, inplace=True)
                logger.info(f"Dynamic quantization applied to {name}")
            elif quant_type == "static":
                # For static, need more preparation; simplified
                module.qconfig = torch.quantization.default_qconfig
                torch.quantization.prepare(module, inplace=True)
                torch.quantization.convert(module, inplace=True)
                logger.info(f"Static quantization applied to {name}")
    return model

# --------------------------------------------------------------------
# 6. Memory and Speed Benchmarks
# --------------------------------------------------------------------
def benchmark_quantization(model_fp32: nn.Module, 
                           model_quantized: nn.Module,
                           test_input: torch.Tensor,
                           iterations: int = 100) -> Dict[str, float]:
    """
    Compare memory usage and inference speed between FP32 and quantized models.
    """
    import time
    import psutil
    import os
    
    results = {}
    
    # Memory usage
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024**2
    
    # FP32 inference
    model_fp32.eval()
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    start = time.time()
    with torch.no_grad():
        for _ in range(iterations):
            _ = model_fp32(test_input)
    fp32_time = (time.time() - start) / iterations * 1000
    mem_after = process.memory_info().rss / 1024**2
    results["fp32_memory_mb"] = mem_after - mem_before
    results["fp32_latency_ms"] = fp32_time
    
    # Quantized inference
    model_quantized.eval()
    mem_before = process.memory_info().rss / 1024**2
    start = time.time()
    with torch.no_grad():
        for _ in range(iterations):
            _ = model_quantized(test_input)
    quant_time = (time.time() - start) / iterations * 1000
    mem_after = process.memory_info().rss / 1024**2
    results["quant_memory_mb"] = mem_after - mem_before
    results["quant_latency_ms"] = quant_time
    results["speedup"] = fp32_time / quant_time if quant_time > 0 else 0
    results["memory_reduction"] = (results["fp32_memory_mb"] - results["quant_memory_mb"]) / results["fp32_memory_mb"] if results["fp32_memory_mb"] > 0 else 0
    
    return results

# --------------------------------------------------------------------
# 7. Integration with CrownStarCore
# --------------------------------------------------------------------
def quantize_for_tier(model: nn.Module, tier: str, calibration_loader: Optional[torch.utils.data.DataLoader] = None) -> nn.Module:
    """
    Apply appropriate quantization based on tier.
    
    - Free: INT8 dynamic quantization (smallest memory)
    - Basic: INT8 dynamic or FP16 (depending on device)
    - Pro/Enterprise: No quantization (FP32 full precision)
    """
    if tier == "free":
        logger.info("Applying INT8 dynamic quantization for Free tier")
        model = apply_dynamic_quantization(model)
    elif tier == "basic":
        if torch.cuda.is_available():
            logger.info("Using FP16 for Basic tier (GPU available)")
            model = convert_to_fp16(model)
        else:
            logger.info("Using INT8 dynamic quantization for Basic tier (CPU)")
            model = apply_dynamic_quantization(model)
    else:
        logger.info("No quantization for Pro/Enterprise tiers")
    return model

def load_quantized_model(model_class, config, tier: str, checkpoint_path: Optional[str] = None, **kwargs) -> nn.Module:
    """
    Load a model with quantization applied based on tier.
    
    Args:
        model_class: The model class (e.g., UnifiedSuperModel)
        config: Model configuration
        tier: 'free', 'basic', 'pro', 'enterprise'
        checkpoint_path: Optional path to pre‑trained weights
    
    Returns:
        Model (possibly quantized)
    """
    # First load FP32 model (or from checkpoint)
    model = model_class(config, **kwargs)
    if checkpoint_path and Path(checkpoint_path).exists():
        state_dict = torch.load(checkpoint_path, map_location='cpu')
        model.load_state_dict(state_dict)
    
    # Apply quantization based on tier
    model = quantize_for_tier(model, tier)
    return model

# --------------------------------------------------------------------
# 8. ONNX Export with Quantization (optional)
# --------------------------------------------------------------------
def export_onnx_quantized(model: nn.Module, 
                          input_example: torch.Tensor, 
                          output_path: str,
                          opset_version: int = 14,
                          quantize: bool = True):
    """
    Export model to ONNX with optional INT8 quantization.
    Note: ONNX runtime quantization requires additional steps.
    """
    model.eval()
    if quantize:
        # Dynamic quantization before ONNX export (weights only)
        model = apply_dynamic_quantization(model)
    
    torch.onnx.export(
        model,
        input_example,
        output_path,
        opset_version=opset_version,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size', 1: 'sequence'}, 'output': {0: 'batch_size'}}
    )
    logger.info(f"ONNX model exported to {output_path}")
    
    # Optional: quantize ONNX using onnxruntime
    if quantize:
        try:
            import onnx
            from onnxruntime.quantization import quantize_dynamic, QuantType
            quantized_path = output_path.replace('.onnx', '_quantized.onnx')
            quantize_dynamic(output_path, quantized_path, weight_type=QuantType.QInt8)
            logger.info(f"ONNX INT8 quantized model saved to {quantized_path}")
        except ImportError:
            logger.warning("onnxruntime not installed; skipping ONNX quantization")

# --------------------------------------------------------------------
# 9. Utility Functions for Model Size Reduction
# --------------------------------------------------------------------
def get_model_size_mb(model: nn.Module) -> float:
    """Calculate model size in megabytes."""
    param_size = sum(p.numel() * p.element_size() for p in model.parameters())
    buffer_size = sum(b.numel() * b.element_size() for b in model.buffers())
    total_bytes = param_size + buffer_size
    return total_bytes / (1024 * 1024)

def prune_model(model: nn.Module, amount: float = 0.3):
    """
    Apply magnitude pruning to reduce model size (for Free tier).
    """
    from torch.nn.utils import prune
    parameters_to_prune = []
    for name, module in model.named_modules():
        if isinstance(module, nn.Linear):
            parameters_to_prune.append((module, 'weight'))
    
    for module, param_name in parameters_to_prune:
        prune.l1_unstructured(module, name=param_name, amount=amount)
        prune.remove(module, param_name)
    
    logger.info(f"Pruned {len(parameters_to_prune)} linear layers with amount={amount}")
    return model

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# FP16 conversion
model_fp16 = convert_to_fp16(model)

# Dynamic quantization (INT8)
quantized = apply_dynamic_quantization(model)

# Static quantization with calibration
calibration_loader = DataLoader(calibration_dataset, batch_size=1)
quantized_static = static_quantize(model, calibration_loader)

# Quantize for Free tier
model_free = quantize_for_tier(model, "free")

# Benchmark
results = benchmark_quantization(model_fp32, quantized, test_input)
print(f"Speedup: {results['speedup']:.2f}x")
"""

# ====================================================================================================
# END OF quantization.py
# ====================================================================================================
