# federated/aggregation/algorithms.py – Aggregation algorithms for federated learning
import numpy as np
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class AggregationResult:
    weights: Dict[str, np.ndarray]
    metadata: dict

def fedavg(updates: List[tuple], global_weights: Dict[str, np.ndarray]) -> AggregationResult:
    """Federated Averaging: weighted average by number of samples"""
    total_samples = sum(samples for _, samples, _ in updates)
    aggregated = {}
    for key in global_weights.keys():
        aggregated[key] = np.zeros_like(global_weights[key])
    for weights, samples, _ in updates:
        weight = samples / total_samples if total_samples > 0 else 1.0 / len(updates)
        for key in aggregated.keys():
            aggregated[key] += weights[key] * weight
    return AggregationResult(aggregated, {"algorithm": "fedavg", "total_samples": total_samples})

def fedprox(updates: List[tuple], global_weights: Dict[str, np.ndarray], mu: float = 0.1) -> AggregationResult:
    """FedProx: adds proximal term (same aggregation as FedAvg, proximal handled during client training)"""
    # Aggregation is same as FedAvg; proximal term is added in client loss
    return fedavg(updates, global_weights)

def fedadam(updates: List[tuple], global_weights: Dict[str, np.ndarray], lr: float = 0.01, beta1: float = 0.9, beta2: float = 0.999) -> AggregationResult:
    """Federated Adam: adaptive aggregation using moment estimates (simplified)"""
    # In real implementation, server maintains momentum buffers
    aggregated = fedavg(updates, global_weights).weights
    # Simplified: return aggregated as is
    return AggregationResult(aggregated, {"algorithm": "fedadam", "lr": lr})

def median_aggregation(updates: List[tuple], global_weights: Dict[str, np.ndarray]) -> AggregationResult:
    """Coordinate‑wise median (robust to Byzantine attacks)"""
    aggregated = {}
    n_updates = len(updates)
    for key in global_weights.keys():
        # Collect all client updates for this parameter
        stacked = np.stack([weights[key] for weights, _, _ in updates], axis=0)
        # Median across clients
        aggregated[key] = np.median(stacked, axis=0)
    return AggregationResult(aggregated, {"algorithm": "median"})

def trimmed_mean(updates: List[tuple], global_weights: Dict[str, np.ndarray], trim_ratio: float = 0.2) -> AggregationResult:
    """Trimmed mean: remove highest and lowest fractions"""
    aggregated = {}
    n_updates = len(updates)
    keep = int(n_updates * (1 - 2 * trim_ratio))
    for key in global_weights.keys():
        stacked = np.stack([weights[key] for weights, _, _ in updates], axis=0)
        sorted_idx = np.argsort(stacked, axis=0)
        # Keep middle 'keep' values
        start = int(n_updates * trim_ratio)
        trimmed = np.take_along_axis(stacked, sorted_idx[start:start+keep], axis=0)
        aggregated[key] = np.mean(trimmed, axis=0)
    return AggregationResult(aggregated, {"algorithm": "trimmed_mean", "trim_ratio": trim_ratio})

# Dictionary of available algorithms
ALGORITHMS = {
    "fedavg": fedavg,
    "fedprox": fedprox,
    "fedadam": fedadam,
    "median": median_aggregation,
    "trimmed_mean": trimmed_mean
}
