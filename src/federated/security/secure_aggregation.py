# federated/security/secure_aggregation.py – Privacy‑preserving aggregation stubs
import numpy as np
from typing import Dict, List
import hashlib

class HomomorphicEncryptionStub:
    """Placeholder for homomorphic encryption (e.g., Paillier, CKKS)"""
    @staticmethod
    def encrypt(value: float) -> bytes:
        # Stub – real implementation would use library like PySEAL, TenSEAL
        return str(value).encode()
    
    @staticmethod
    def decrypt(encrypted: bytes) -> float:
        return float(encrypted.decode())
    
    @staticmethod
    def add(enc1: bytes, enc2: bytes) -> bytes:
        v1 = float(enc1.decode())
        v2 = float(enc2.decode())
        return str(v1 + v2).encode()

class DifferentialPrivacy:
    """Add Gaussian or Laplace noise to updates"""
    def __init__(self, epsilon: float = 1.0, delta: float = 1e-5):
        self.epsilon = epsilon
        self.delta = delta
        self.sensitivity = 1.0
    
    def add_gaussian_noise(self, weights: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        sigma = np.sqrt(2 * np.log(1.25 / self.delta)) * self.sensitivity / self.epsilon
        noisy = {}
        for key, val in weights.items():
            noise = np.random.normal(0, sigma, size=val.shape)
            noisy[key] = val + noise
        return noisy
    
    def add_laplace_noise(self, weights: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        scale = self.sensitivity / self.epsilon
        noisy = {}
        for key, val in weights.items():
            noise = np.random.laplace(0, scale, size=val.shape)
            noisy[key] = val + noise
        return noisy

def client_update_with_privacy(weights: Dict[str, np.ndarray], epsilon: float = 1.0) -> Dict[str, np.ndarray]:
    dp = DifferentialPrivacy(epsilon=epsilon)
    return dp.add_gaussian_noise(weights)
