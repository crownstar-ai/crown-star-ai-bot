# ====================================================================================================
# gpu_utils.py – GPU utilities for CrownStar‑Absolute
# Features:
#   - CUDA memory management (clear cache, memory stats, fragmentation reduction)
#   - Mixed precision training helpers (autocast, GradScaler)
#   - GPU device selection and information
#   - Memory pooling and efficient allocation
#   - Fallback to CPU when CUDA unavailable
#   - Integration with PyTorch AMP (automatic mixed precision)
# ====================================================================================================

import torch
import gc
import os
import math
import threading
import time
from typing import Optional, Tuple, Dict, Any, List
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# ====================================================================================================
# 1. GPU Availability and Device Management
# ====================================================================================================

def is_cuda_available() -> bool:
    """Check if CUDA is available and functional."""
    return torch.cuda.is_available()

def get_gpu_info() -> Dict[str, Any]:
    """Return detailed information about available GPUs."""
    if not is_cuda_available():
        return {"available": False, "message": "CUDA not available"}
    
    devices = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        devices.append({
            "index": i,
            "name": props.name,
            "total_memory_gb": round(props.total_memory / 1e9, 2),
            "compute_capability": f"{props.major}.{props.minor}",
            "multiprocessor_count": props.multi_processor_count,
        })
    
    # Get current memory stats
    current_device = torch.cuda.current_device()
    allocated = torch.cuda.memory_allocated(current_device) / 1e9
    reserved = torch.cuda.memory_reserved(current_device) / 1e9
    free = (torch.cuda.get_device_properties(current_device).total_memory - reserved) / 1e9
    
    return {
        "available": True,
        "device_count": torch.cuda.device_count(),
        "current_device": current_device,
        "current_device_name": torch.cuda.get_device_name(current_device),
        "devices": devices,
        "memory_allocated_gb": round(allocated, 2),
        "memory_reserved_gb": round(reserved, 2),
        "memory_free_gb": round(free, 2),
        "memory_used_percent": round((allocated / devices[0]["total_memory_gb"]) * 100, 1) if devices else 0
    }

def select_device(device_id: Optional[int] = None, prefer_cuda: bool = True) -> torch.device:
    """
    Select the best available device.
    
    Args:
        device_id: Specific GPU index (if None, auto‑select)
        prefer_cuda: If False, always use CPU
    
    Returns:
        torch.device
    """
    if not prefer_cuda or not is_cuda_available():
        logger.info("Using CPU device")
        return torch.device("cpu")
    
    if device_id is not None and device_id < torch.cuda.device_count():
        device = torch.device(f"cuda:{device_id}")
        logger.info(f"Using selected GPU: {torch.cuda.get_device_name(device_id)}")
        return device
    
    # Auto‑select: choose GPU with most free memory
    max_free = -1
    best_id = 0
    for i in range(torch.cuda.device_count()):
        torch.cuda.set_device(i)
        free = torch.cuda.get_device_properties(i).total_memory - torch.cuda.memory_reserved(i)
        if free > max_free:
            max_free = free
            best_id = i
    
    torch.cuda.set_device(best_id)
    logger.info(f"Auto‑selected GPU {best_id}: {torch.cuda.get_device_name(best_id)} "
                f"(free memory: {max_free / 1e9:.2f} GB)")
    return torch.device(f"cuda:{best_id}")

# ====================================================================================================
# 2. CUDA Memory Management
# ====================================================================================================

def clear_cuda_cache():
    """Clear CUDA cache and collect garbage."""
    if not is_cuda_available():
        return
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    logger.debug("CUDA cache cleared")

def get_cuda_memory_stats(device: Optional[int] = None) -> Dict[str, float]:
    """Get detailed memory statistics for a GPU device."""
    if not is_cuda_available():
        return {"error": "CUDA not available"}
    
    device = device if device is not None else torch.cuda.current_device()
    
    allocated = torch.cuda.memory_allocated(device) / 1e9
    reserved = torch.cuda.memory_reserved(device) / 1e9
    total = torch.cuda.get_device_properties(device).total_memory / 1e9
    free = total - reserved
    allocated_max = torch.cuda.max_memory_allocated(device) / 1e9
    reserved_max = torch.cuda.max_memory_reserved(device) / 1e9
    
    return {
        "device": device,
        "allocated_gb": round(allocated, 2),
        "reserved_gb": round(reserved, 2),
        "free_gb": round(free, 2),
        "total_gb": round(total, 2),
        "allocated_percent": round((allocated / total) * 100, 1),
        "max_allocated_gb": round(allocated_max, 2),
        "max_reserved_gb": round(reserved_max, 2),
    }

def reduce_memory_fragmentation():
    """
    Reduce CUDA memory fragmentation by clearing cache and performing
    a simple allocation‑deallocation cycle.
    """
    if not is_cuda_available():
        return
    # Force a small allocation and free to coalesce memory
    torch.cuda.empty_cache()
    tmp = torch.empty(1024 * 1024, device='cuda')  # 1 MB
    del tmp
    torch.cuda.empty_cache()
    logger.debug("Memory fragmentation reduction complete")

def get_optimal_batch_size(model, input_size: Tuple[int, ...] = (1, 512), 
                           max_batch_size: int = 64, step: int = 8) -> int:
    """
    Dynamically determine the maximum batch size that fits in GPU memory.
    
    Args:
        model: PyTorch model
        input_size: Shape of a single input (batch dimension excluded)
        max_batch_size: Upper bound to test
        step: Step size for binary search
    
    Returns:
        Maximum batch size that fits in GPU memory
    """
    if not is_cuda_available():
        return 1
    
    model.eval()
    model = model.cuda()
    
    def try_batch(batch_size: int) -> bool:
        try:
            dummy = torch.randn(batch_size, *input_size[1:]).cuda()
            with torch.no_grad():
                _ = model(dummy)
            del dummy
            torch.cuda.empty_cache()
            return True
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                torch.cuda.empty_cache()
                return False
            raise
    
    # Binary search
    low, high = 1, max_batch_size
    best = 1
    while low <= high:
        mid = (low + high) // 2
        if try_batch(mid):
            best = mid
            low = mid + 1
        else:
            high = mid - 1
    
    logger.info(f"Optimal batch size determined: {best}")
    return best

# ====================================================================================================
# 3. Mixed Precision Helpers (AMP)
# ====================================================================================================

@contextmanager
def autocast_context(enabled: bool = True, dtype: torch.dtype = torch.float16):
    """
    Context manager for automatic mixed precision.
    Usage:
        with autocast_context():
            output = model(input)
    """
    if enabled and is_cuda_available():
        with torch.cuda.amp.autocast(dtype=dtype):
            yield
    else:
        yield

class AMPTrainerHelper:
    """
    Helper class for mixed precision training.
    Manages GradScaler, autocast, and gradient scaling.
    """
    
    def __init__(self, enabled: bool = True, init_scale: float = 2**16, growth_factor: float = 2.0,
                 backoff_factor: float = 0.5, growth_interval: int = 2000):
        """
        Args:
            enabled: Enable mixed precision training
            init_scale: Initial scale factor
            growth_factor: Multiplier when no overflow
            backoff_factor: Multiplier when overflow occurs
            growth_interval: Steps between growth attempts
        """
        self.enabled = enabled and is_cuda_available()
        self.scaler = torch.cuda.amp.GradScaler(
            init_scale=init_scale,
            growth_factor=growth_factor,
            backoff_factor=backoff_factor,
            growth_interval=growth_interval
        ) if self.enabled else None
        self._overflow_count = 0
    
    def scale_loss(self, loss: torch.Tensor) -> torch.Tensor:
        """Scale loss for mixed precision backward."""
        if self.enabled:
            return self.scaler.scale(loss)
        return loss
    
    def step(self, optimizer: torch.optim.Optimizer):
        """Unscale gradients and perform optimizer step."""
        if self.enabled:
            self.scaler.step(optimizer)
            self.scaler.update()
        else:
            optimizer.step()
    
    def unscale_(self, optimizer: torch.optim.Optimizer):
        """Unscale gradients (useful before gradient clipping)."""
        if self.enabled:
            self.scaler.unscale_(optimizer)
    
    def state_dict(self) -> Dict:
        """Return scaler state for checkpointing."""
        if self.enabled:
            return self.scaler.state_dict()
        return {}
    
    def load_state_dict(self, state_dict: Dict):
        """Load scaler state from checkpoint."""
        if self.enabled and state_dict:
            self.scaler.load_state_dict(state_dict)
    
    def is_overflow(self) -> bool:
        """Check if last step overflowed (requires custom tracking)."""
        # GradScaler doesn't expose overflow directly; we approximate
        return False

# ====================================================================================================
# 4. Memory Pooling for Large Tensors
# ====================================================================================================

class TensorMemoryPool:
    """
    Simple memory pool for reusing large tensors to reduce allocation overhead.
    Useful for transformers with fixed sequence lengths.
    """
    
    def __init__(self, device: torch.device = None):
        self.device = device or torch.device("cuda" if is_cuda_available() else "cpu")
        self._pools: Dict[Tuple[int, ...], List[torch.Tensor]] = {}
        self._lock = threading.Lock()
    
    def get(self, shape: Tuple[int, ...], dtype: torch.dtype = torch.float32) -> torch.Tensor:
        """Get a tensor from the pool or create a new one."""
        key = (shape, dtype)
        with self._lock:
            pool = self._pools.get(key, [])
            if pool:
                tensor = pool.pop()
                tensor.zero_()
                return tensor
        return torch.zeros(shape, dtype=dtype, device=self.device)
    
    def release(self, tensor: torch.Tensor):
        """Return a tensor to the pool for reuse."""
        key = (tensor.shape, tensor.dtype)
        with self._lock:
            if key not in self._pools:
                self._pools[key] = []
            # Avoid accumulating too many tensors of same shape
            if len(self._pools[key]) < 10:
                self._pools[key].append(tensor)
    
    def clear(self):
        """Clear all pooled tensors."""
        with self._lock:
            self._pools.clear()
        gc.collect()
        if is_cuda_available():
            torch.cuda.empty_cache()
    
    def stats(self) -> Dict:
        """Return statistics about the pool."""
        with self._lock:
            total_tensors = sum(len(v) for v in self._pools.values())
            return {"total_tensors": total_tensors, "unique_shapes": len(self._pools)}

# ====================================================================================================
# 5. GPU Monitoring and Health Checks
# ====================================================================================================

class GPUMonitor:
    """
    Monitors GPU usage, temperature, and power consumption.
    Provides logging and alerting hooks.
    """
    
    def __init__(self, interval_seconds: int = 60, log_threshold_percent: float = 90.0):
        self.interval = interval_seconds
        self.threshold = log_threshold_percent
        self._running = False
        self._thread = None
        self._callbacks = []
    
    def start(self):
        """Start background monitoring thread."""
        if self._running or not is_cuda_available():
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("GPU monitor started")
    
    def stop(self):
        """Stop monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def add_callback(self, callback):
        """Add callback function that receives GPU stats dict."""
        self._callbacks.append(callback)
    
    def _monitor_loop(self):
        while self._running:
            try:
                stats = get_gpu_info()
                if stats.get("available"):
                    memory_percent = stats.get("memory_used_percent", 0)
                    if memory_percent > self.threshold:
                        logger.warning(f"GPU memory usage high: {memory_percent}%")
                    for cb in self._callbacks:
                        cb(stats)
            except Exception as e:
                logger.debug(f"GPU monitor error: {e}")
            time.sleep(self.interval)
    
    @staticmethod
    def get_temperature(device: int = 0) -> Optional[int]:
        """Get GPU temperature using nvidia-smi (if available)."""
        if not is_cuda_available():
            return None
        try:
            import subprocess
            output = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'],
                text=True
            ).strip().split('\n')
            if device < len(output):
                return int(output[device])
        except Exception:
            pass
        return None

# ====================================================================================================
# 6. Automatic Mixed Precision Training Wrapper
# ====================================================================================================

class MixedPrecisionTrainer:
    """
    Complete wrapper for mixed precision training that handles:
    - Autocast context
    - Gradient scaling
    - Gradient clipping with unscaling
    - Loss scaling adjustments
    """
    
    def __init__(self, model: torch.nn.Module, optimizer: torch.optim.Optimizer,
                 enabled: bool = True, grad_clip_norm: float = 1.0):
        self.model = model
        self.optimizer = optimizer
        self.enabled = enabled and is_cuda_available()
        self.grad_clip_norm = grad_clip_norm
        self.scaler = torch.cuda.amp.GradScaler() if self.enabled else None
    
    def train_step(self, loss_fn, *inputs, **kwargs) -> torch.Tensor:
        """
        Perform a single training step with mixed precision.
        
        Args:
            loss_fn: Function that takes model outputs and returns loss
            *inputs, **kwargs: Passed to model.forward()
        
        Returns:
            loss value (scalar)
        """
        self.model.train()
        self.optimizer.zero_grad()
        
        if self.enabled:
            with torch.cuda.amp.autocast():
                outputs = self.model(*inputs, **kwargs)
                loss = loss_fn(outputs)
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip_norm)
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            outputs = self.model(*inputs, **kwargs)
            loss = loss_fn(outputs)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip_norm)
            self.optimizer.step()
        
        return loss.detach().item()
    
    def state_dict(self) -> Dict:
        """Save scaler state."""
        if self.enabled:
            return {"scaler": self.scaler.state_dict()}
        return {}
    
    def load_state_dict(self, state: Dict):
        """Load scaler state."""
        if self.enabled and "scaler" in state:
            self.scaler.load_state_dict(state["scaler"])

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
# Get GPU info
info = get_gpu_info()
print(f"CUDA available: {info['available']}")

# Select best device
device = select_device()
print(f"Using device: {device}")

# Clear cache before large allocation
clear_cuda_cache()

# Use mixed precision context
with autocast_context():
    output = model(input)

# Create AMP trainer helper
amp_helper = AMPTrainerHelper(enabled=True)
# Inside training loop:
loss = amp_helper.scale_loss(loss)
loss.backward()
amp_helper.step(optimizer)

# Monitor GPU
monitor = GPUMonitor()
monitor.start()
"""

# ====================================================================================================
# END OF gpu_utils.py
# ====================================================================================================
