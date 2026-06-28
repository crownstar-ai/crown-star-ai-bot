# optimization/qubo/solver.py – QUBO solver (brute‑force, greedy, simulated annealing)
import numpy as np
import random
import math
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
import itertools

@dataclass
class QUBOProblem:
    """QUBO problem: minimize x^T Q x, where x in {0,1}^n"""
    Q: np.ndarray  # n x n matrix (can be symmetric)
    n: int
    name: str = ""

class QUBOSolver:
    def __init__(self, problem: QUBOProblem):
        self.problem = problem
        self.Q = problem.Q
        self.n = problem.n
    
    def evaluate(self, x: np.ndarray) -> float:
        """Compute objective value: x^T Q x"""
        return x @ self.Q @ x
    
    def brute_force(self) -> Tuple[np.ndarray, float]:
        """Exhaustive search (only for n <= 20)"""
        if self.n > 20:
            raise ValueError("Brute‑force only for n <= 20")
        best_x = None
        best_val = float('inf')
        for bits in itertools.product([0,1], repeat=self.n):
            x = np.array(bits)
            val = self.evaluate(x)
            if val < best_val:
                best_val = val
                best_x = x.copy()
        return best_x, best_val
    
    def greedy(self, max_iters: int = 100) -> Tuple[np.ndarray, float]:
        """Greedy local search: flip one bit at a time"""
        x = np.random.randint(0, 2, size=self.n)
        best_val = self.evaluate(x)
        improved = True
        iter_count = 0
        while improved and iter_count < max_iters:
            improved = False
            for i in range(self.n):
                x_flip = x.copy()
                x_flip[i] = 1 - x_flip[i]
                new_val = self.evaluate(x_flip)
                if new_val < best_val:
                    x = x_flip
                    best_val = new_val
                    improved = True
            iter_count += 1
        return x, best_val
    
    def simulated_annealing(self, initial_temp: float = 100.0, cooling_rate: float = 0.99, max_iters: int = 1000) -> Tuple[np.ndarray, float]:
        """Simulated annealing for QUBO"""
        x = np.random.randint(0, 2, size=self.n)
        current_val = self.evaluate(x)
        best_x = x.copy()
        best_val = current_val
        temp = initial_temp
        for _ in range(max_iters):
            # Random flip
            i = random.randint(0, self.n-1)
            x_new = x.copy()
            x_new[i] = 1 - x_new[i]
            new_val = self.evaluate(x_new)
            delta = new_val - current_val
            if delta < 0 or random.random() < math.exp(-delta / temp):
                x = x_new
                current_val = new_val
                if current_val < best_val:
                    best_val = current_val
                    best_x = x.copy()
            temp *= cooling_rate
        return best_x, best_val

def create_random_qubo(n: int, seed: int = None) -> QUBOProblem:
    """Generate random QUBO problem for testing"""
    if seed:
        np.random.seed(seed)
    Q = np.random.randn(n, n) * 2
    # Make symmetric: (Q + Q.T)/2
    Q = (Q + Q.T) / 2
    # Ensure diagonal positive (optional)
    np.fill_diagonal(Q, np.abs(np.diag(Q)))
    return QUBOProblem(Q, n, f"random_{n}")
